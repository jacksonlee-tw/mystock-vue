"""
industry_chain/extractor.py
LLM 產業鏈知識萃取管線（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.7）。

Stage B 單階段萃取（FR-3／FR-3a／FR-3b），加上 §4.7.7 的兩段式 grounded 萃取（ADR-IC-17，
`IC_LLM_GROUNDING_ENABLED` 控制開關，關閉時行為與只有 Stage B 時完全一致，見 AC-IC-24）——
Stage A 本體在 research.py，這裡只負責「要不要呼叫它、呼叫失敗要不要讓整條鏈失敗」的整合。
呼叫路徑：G1～G4 閘門 →〔選擇性 Stage A 研究〕→ 佔位寫入 pending 執行紀錄 → 呼叫 LLM →
原始回應先落地 JSON 快照（無論校驗結果如何都保留）→ 五道機器校驗（validator.py）→ 通過的邊
best-effort 雙寫 → 成功／失敗收尾（ai_llm_execution ＋ activity_log）。

比照 api/v1/endpoints/ai_analysis.py 的 analyze_stock() 兩階段交易精神：呼叫 LLM 前的佔位寫入
先 commit、不在呼叫 LLM 期間持有 DB 交易；但本模組的成本閘門是自建的輕量版（§4.7.5），不複用
ai/guard.py 的六道閘門（那是圍繞 ai_analysis_report 唯一鍵設計的，本模組沒有 symbol/trade_date
可以填，見規格書 §2.5 的可複用性盤點）。
"""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime

from ai import config as ai_config
from ai.providers import get_provider
from config import DATA_DIR
from db.dual_write import dual_write_industry_chain_edges
from db.session import get_async_session
from industry_chain import config as ic_config
from industry_chain import prompt as ic_prompt
from industry_chain import research as ic_research
from industry_chain import validator as ic_validator
from industry_chain.errors import (
    IndustryChainCapExceededException, IndustryChainCrawlInProgressException,
    IndustryChainDisabledException, IndustryChainModelInvalidException,
    IndustryChainNoKeyException, IndustryChainNotFoundException,
)
from industry_chain.schema import ChainExtractionResult
from repositories.activity_log_repository import ActivityLogRepository
from repositories.ai_execution_repository import AIExecutionRepository
from repositories.stock_repository import StockRepository

logger = logging.getLogger("mystock-backend")

VIEW_ID = "industry_chain_extract"
PROMPT_VERSION = "v1"
MAX_EDGES_PER_CHAIN = 80

# G2 單一飛行中：模組級旗標，涵蓋排程與手動觸發共用（比照 fetch_status 精神，簡化為單一布林，
# 見 §4.7.5）。行程重啟即重置，不需要跨行程持久化——本來就是「排程與手動觸發互斥」這種
# 單一 uvicorn 程序內的短暫防重入，不是需要存活過重啟的狀態。
_in_progress = False


def _snapshot_path(chain_id: str, when: datetime | None = None) -> str:
    when = when or datetime.now()
    snap_dir = os.path.join(DATA_DIR, "_industry_chain")
    os.makedirs(snap_dir, exist_ok=True)
    return os.path.join(snap_dir, f"llm_snapshot_{chain_id}_{when.strftime('%Y%m')}.json")


def _save_snapshot(chain_id: str, raw: dict) -> None:
    """原始回應**先**落地，無論後面校驗結果如何都保留（FR-3b）。同一鏈同一個月覆寫——
    每月只跑一次（FR-18），不需要保留同月多次呼叫的歷史版本。"""
    try:
        with open(_snapshot_path(chain_id), "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.warning(f"[產業鏈] {chain_id} JSON 快照落地失敗（不影響萃取結果）: {e}")


def _estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    pricing = ai_config.get_model_pricing(model)
    if not pricing or input_tokens is None or output_tokens is None:
        return None
    return round(input_tokens / 1_000_000 * pricing["input"] + output_tokens / 1_000_000 * pricing["output"], 6)


async def _get_leader_names(symbols: list[str]) -> dict[str, str]:
    rows = await StockRepository().get_symbols(symbols, "tw") if symbols else []
    return {row["symbol"]: row["name"] for row in rows}


def _build_research_context(research_result: dict) -> str:
    """把 Stage A 的研究文字＋引用來源整理成一段附加在 Stage B User Prompt 尾端的文字
    （§4.7.7）。刻意標「供參考」而非直接當成事實陳述——Stage B 仍要跑完整套五道機器校驗，
    Stage A 只是多給一份「近期」的參考資料，不代表 Stage A 的內容本身已被驗證過。"""
    lines = [
        "\n\n【近期網路研究補充資料（供參考，仍須依你自己的判斷篩選，不代表以下內容已被驗證）】",
        research_result["text"] or "（查無研究內容）",
    ]
    if research_result["citations"]:
        lines.append("引用來源：")
        lines.extend(
            f"- {c.get('title') or '(無標題)'}（{c['url']}）" for c in research_result["citations"]
        )
    return "\n".join(lines)


def _match_evidence_url(up_symbol: str, down_symbol: str, names: dict[str, str], citations: list[dict]) -> str:
    """設計判斷（已於計畫中明確告知）：Stage A 回傳的是整條鏈的一批引用來源，不是逐筆邊各自
    對應一個來源。用簡單啟發式——標題同時包含該邊上游與下游公司簡稱的第一筆引用來源即視為
    evidence_url；找不到就留空字串。保證的是「絕不是模型生成的假網址」（AC-IC-25 的底線），
    不保證比對到的來源就是這條供應鏈關係最貼切的佐證。"""
    up_name, down_name = names.get(up_symbol, ""), names.get(down_symbol, "")
    if not up_name or not down_name:
        return ""
    for c in citations:
        title = c.get("title") or ""
        if up_name in title and down_name in title:
            return c.get("url", "")
    return ""


async def _monthly_call_count() -> int:
    """本月（Asia/Taipei 概念上約等於伺服器本機時間）已產生的萃取呼叫數，用於 G3 上限判斷。
    直接查 ai_llm_execution，不另建計數表——成本紀錄的唯一事實來源不變（ADR-AI-17）。"""
    from sqlalchemy import text
    async with get_async_session() as session:
        result = await session.execute(
            text("""
                SELECT COUNT(*) FROM ai_llm_execution
                 WHERE view_id = :view_id AND created_at >= date_trunc('month', CURRENT_DATE)
            """),
            {"view_id": VIEW_ID}
        )
        return result.scalar() or 0


async def extract_chain(chain_id: str, *, provider_code: str | None = None, model: str | None = None) -> dict:
    """對單一產業鏈觸發一次 LLM 知識萃取。回傳摘要 dict（`status` 為
    `skipped` / `succeeded` / `failed`），供排程與 API 端點記錄。"""
    global _in_progress

    # G1：功能旗標（AC-IC-15：未啟用時完全不得碰資料庫或外部 API）
    if not ic_config.is_enabled():
        raise IndustryChainDisabledException("產業鏈知識圖譜功能未啟用")

    chain = ic_config.get_chain(chain_id)
    if chain is None:
        raise IndustryChainNotFoundException(f"找不到產業鏈：{chain_id}")
    if not chain.downstream_leaders:
        # §6.1 既有限制：沒有下游龍頭就沒有 User Prompt 的錨點，無法組成萃取請求
        return {"status": "skipped", "reason": "no_downstream_leaders", "chain_id": chain_id}

    # G2：單一飛行中
    if _in_progress:
        raise IndustryChainCrawlInProgressException("已有產業鏈萃取工作執行中")

    provider_code = (provider_code or "gemini").lower()
    if provider_code not in ai_config.VALID_PROVIDERS:
        raise IndustryChainModelInvalidException(f"不支援的 provider：{provider_code}")
    model = model or (ai_config.get_gemini_model() if provider_code == "gemini" else ai_config.get_claude_model())

    # G4：模型白名單（ADR-AI-22，先於 G3 檢查——打錯模型不該先扣掉一次月配額才發現）
    if not ai_config.is_valid_model(provider_code, model):
        raise IndustryChainModelInvalidException(f"{provider_code} 不支援的模型：{model}")

    # 未設金鑰時直接擋在佔位寫入之前，不佔用一列執行紀錄
    api_key = ai_config.get_gemini_api_key() if provider_code == "gemini" else ai_config.get_claude_api_key()
    if not api_key:
        raise IndustryChainNoKeyException(f"{provider_code} 尚未設定 API 金鑰")

    # G3：本月呼叫上限
    if await _monthly_call_count() >= ai_config.get_industry_chain_monthly_call_cap():
        raise IndustryChainCapExceededException(
            f"本月產業鏈萃取呼叫已達上限（{ai_config.get_industry_chain_monthly_call_cap()}）"
        )

    _in_progress = True
    try:
        return await _run_extraction(chain, provider_code, model)
    finally:
        _in_progress = False


async def _run_extraction(chain, provider_code: str, model: str) -> dict:
    leader_names = await _get_leader_names(chain.downstream_leaders)
    system_prompt = ic_prompt.SYSTEM_PROMPT
    user_prompt = ic_prompt.build_user_prompt(chain, leader_names)

    # §4.7.7 兩段式 grounded 萃取 Stage A（ADR-IC-17）：關閉時完全跳過，行為與只有 Stage B 時
    # 一模一樣（AC-IC-24）。開啟時讓 research.run_research_stage() 的例外直接往上拋出——它內部
    # 已經自己記過 IC_LLM_RESEARCH_FAILED，這裡不得吞掉改成靜默跳過 Stage A 直接跑 Stage B，
    # 那比整條鏈直接失敗有害得多（AC-IC-26：一份看起來正常、實際上是純記憶的結果）。
    research_result: dict | None = None
    if ic_config.grounding_enabled():
        research_model = ic_config.get_research_model() or model
        research_result = await ic_research.run_research_stage(chain, leader_names, provider_code, research_model)
        user_prompt = user_prompt + _build_research_context(research_result)

    # 佔位寫入 pending 執行紀錄並 commit（呼叫 LLM 前先寫，中止也留下紀錄；§5.7 關鍵約束）
    async with get_async_session() as session:
        exec_repo = AIExecutionRepository(session)
        execution_id = await exec_repo.start(
            report_id=None, provider=provider_code, model=model,
            symbol=None, market=None, trade_date=None, attempt_no=1,
            prompt_version=PROMPT_VERSION,
            request_meta={
                "chain_id": chain.chain_id, "max_output_tokens": ai_config.get_max_output_tokens(),
                "grounded": research_result is not None,
            },
            view_id=VIEW_ID,
        )
        await session.commit()

    try:
        provider_impl = get_provider(provider_code)
        result = await provider_impl.extract_structured(
            system_prompt, user_prompt, ChainExtractionResult, model=model,
        )
    except Exception as exc:
        await _record_failure(execution_id, error_code=type(exc).__name__, error_message=str(exc), chain_id=chain.chain_id)
        raise

    # 原始回應先落地（FR-3b）——即使後面校驗失敗，快照仍保留供重跑
    raw = result.data.model_dump() if result.data is not None else {"chain_id": chain.chain_id, "edges": [], "notes": "(no parsed output)"}
    _save_snapshot(chain.chain_id, raw)

    if result.data is None:
        await _record_failure(execution_id, error_code="IC_LLM_NO_PARSED_OUTPUT",
                               error_message="LLM 回應無法解析為結構化輸出", chain_id=chain.chain_id)
        return {"status": "failed", "chain_id": chain.chain_id, "reason": "no_parsed_output"}

    outcome = await ic_validator.validate_extraction(
        result.data, chain_id=chain.chain_id, truncated=result.truncated, max_edges=MAX_EDGES_PER_CHAIN,
    )

    if outcome.batch_rejected:
        code = "IC_LLM_TRUNCATED" if result.truncated else "IC_LLM_TOO_MANY_EDGES"
        await _record_failure(execution_id, error_code=code, error_message=outcome.batch_rejected, chain_id=chain.chain_id)
        return {"status": "failed", "chain_id": chain.chain_id, "reason": outcome.batch_rejected}

    if not outcome.accepted:
        reasons = "; ".join(f"{r.upstream_symbol}->{r.downstream_symbol}: {r.reason}" for r in outcome.rejected)[:1000]
        await _record_failure(execution_id, error_code="IC_LLM_ALL_REJECTED",
                               error_message=f"全部 {len(outcome.rejected)} 筆皆未通過校驗: {reasons}",
                               chain_id=chain.chain_id)
        return {"status": "failed", "chain_id": chain.chain_id, "reason": "all_rejected", "rejected_count": len(outcome.rejected)}

    source = f"llm_{provider_code}"
    edge_names: dict[str, str] = {}
    if research_result is not None and outcome.accepted:
        edge_symbols = sorted({e["upstream_symbol"] for e in outcome.accepted} | {e["downstream_symbol"] for e in outcome.accepted})
        edge_names = await _get_leader_names(edge_symbols)
    for edge in outcome.accepted:
        edge["source"] = source
        extra_data = {
            **edge.get("extra_data", {}),
            "llm_model": model, "llm_prompt_version": PROMPT_VERSION, "llm_execution_id": execution_id,
        }
        if research_result is not None:
            extra_data["grounded"] = True
            extra_data["research_snapshot"] = research_result["snapshot_filename"]
            extra_data["evidence_url"] = _match_evidence_url(
                edge["upstream_symbol"], edge["downstream_symbol"], edge_names, research_result["citations"],
            )
        edge["extra_data"] = extra_data
    await dual_write_industry_chain_edges(outcome.accepted)

    if outcome.rejected:
        summary = "; ".join(f"{r.upstream_symbol}->{r.downstream_symbol}: {r.reason}" for r in outcome.rejected)[:1000]
        async with get_async_session() as session:
            await ActivityLogRepository(session).log(
                "IC_LLM_REJECT", view_id=VIEW_ID, success=True, rel_id=execution_id,
                detail=f"{chain.chain_id}: {len(outcome.rejected)} 筆遭拒",
                comments=summary,
            )
            await session.commit()

    est_cost = _estimate_cost(model, result.input_tokens, result.output_tokens)
    async with get_async_session() as session:
        await AIExecutionRepository(session).mark_succeeded(
            execution_id, stop_reason=result.stop_reason, response_meta=result.response_meta,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=None, cache_write_tokens=None,
            image_bytes=None, estimated_cost_usd=est_cost,
            elapsed_ms=result.response_meta.get("elapsed_ms"),
        )
        await ActivityLogRepository(session).log(
            "IC_LLM_EXTRACT_SUCCESS", view_id=VIEW_ID, success=True, rel_id=execution_id,
            detail=f"{chain.chain_id}: {len(outcome.accepted)} 筆通過、{len(outcome.rejected)} 筆遭拒",
        )
        await session.commit()

    return {
        "status": "succeeded", "chain_id": chain.chain_id,
        "accepted": len(outcome.accepted), "rejected": len(outcome.rejected),
    }


async def _record_failure(execution_id: int, *, error_code: str, error_message: str, chain_id: str) -> None:
    """收尾寫入吞例外只記警告——呼叫 LLM 之後的失敗不該讓「已經花掉的呼叫沒有紀錄」
    （§4.7 共同規範，比照 ai/recorder.py 的既有立場）。"""
    try:
        async with get_async_session() as session:
            await AIExecutionRepository(session).mark_failed(
                execution_id, error_code=error_code[:40], error_message=error_message,
            )
            await ActivityLogRepository(session).log(
                "IC_LLM_EXTRACT_FAILED", view_id=VIEW_ID, success=False, rel_id=execution_id,
                detail=chain_id, comments=f"{error_code}: {error_message}"[:1024],
            )
            await session.commit()
    except Exception:
        logger.exception(f"[產業鏈] {chain_id} 失敗收尾寫入資料庫時再度失敗（已略過）")
