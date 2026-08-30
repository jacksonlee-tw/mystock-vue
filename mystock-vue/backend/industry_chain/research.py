"""
industry_chain/research.py
§4.7.7 兩段式 grounded 萃取的 Stage A：開檢索工具做「研究」，不做結構化輸出（見
docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md ADR-IC-17）。

Stage A 是一次獨立的、真實計費的 LLM 呼叫，佔自己一列 `ai_llm_execution`——`view_id` 刻意設為
`"industry_chain_research"`，跟 Stage B 的 `"industry_chain_extract"` 分開（見
extractor.py 的說明：`IC_LLM_MONTHLY_CALL_CAP` 數的是「每月幾次鏈萃取嘗試」，Stage A 是一次
嘗試裡的子步驟，不是另一次獨立嘗試，沿用同一個 view_id 會讓開啟 grounding 後有效月配額被砍半）。

失敗一律把例外往上拋，呼叫端（extractor.py）依 AC-IC-26 把整條鏈的本次萃取視為失敗，
**不得**靜默跳過 Stage A 直接進 Stage B——那會產出一份看起來正常、實際上是純記憶的結果。
"""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime

from ai import config as ai_config
from ai.providers import get_provider
from config import DATA_DIR
from db.session import get_async_session
from industry_chain import config as ic_config
from industry_chain import prompt as ic_prompt
from repositories.activity_log_repository import ActivityLogRepository
from repositories.ai_execution_repository import AIExecutionRepository

logger = logging.getLogger("mystock-backend")

VIEW_ID = "industry_chain_research"
PROMPT_VERSION = "v1"


def _snapshot_path(chain_id: str, when: datetime | None = None) -> str:
    when = when or datetime.now()
    snap_dir = os.path.join(DATA_DIR, "_industry_chain")
    os.makedirs(snap_dir, exist_ok=True)
    return os.path.join(snap_dir, f"llm_research_{chain_id}_{when.strftime('%Y%m')}.json")


def _save_snapshot(chain_id: str, raw: dict) -> str:
    """原始研究結果落地，回傳只含檔名（不含路徑）的字串——extractor.py 要把「用的是哪份研究
    快照」記進邊的 extra_data，只需要檔名可供日後對照，不需要完整路徑（路徑本身是部署環境的
    細節，不該混進資料庫內容裡）。落地失敗只記警告：快照遺失不影響 Stage A 本身已經拿到的結果，
    不該讓整條鏈因此判定失敗（跟 extractor.py 的 Stage B 快照是同一個容錯立場）。"""
    path = _snapshot_path(chain_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.warning(f"[產業鏈] {chain_id} 研究快照落地失敗（不影響本次 Stage A 結果）: {e}")
    return os.path.basename(path)


def _estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """跟 extractor.py 的 _estimate_cost() 是同一套算法，但這裡算出來的數字**只反映 token
    用量**——檢索查詢本身在多數 Provider 是另外按次計費，不會出現在 token 數裡，所以這是
    ADR-IC-18 講的「刻意的低估」，不是計算錯誤。呼叫端把 response_meta.cost_is_partial_estimate
    設為 True 明確標示這件事，而不是假裝這個數字很精確。"""
    pricing = ai_config.get_model_pricing(model)
    if not pricing or input_tokens is None or output_tokens is None:
        return None
    return round(input_tokens / 1_000_000 * pricing["input"] + output_tokens / 1_000_000 * pricing["output"], 6)


async def run_research_stage(chain, leader_names: dict[str, str], provider_code: str, model: str) -> dict:
    """執行 Stage A。成功回傳
    `{"text", "citations": [{"url","title"}], "query_count", "snapshot_filename"}`；
    失敗一律拋例外（見檔頭說明，呼叫端負責判斷是否中止整條鏈）。"""
    system_prompt = ic_prompt.RESEARCH_SYSTEM_PROMPT
    lookback_months = ic_config.get_research_lookback_months()
    user_prompt = ic_prompt.build_research_user_prompt(chain, leader_names, lookback_months)
    timeout_sec = ic_config.get_grounding_timeout_sec()

    # 佔位寫入 pending 執行紀錄並 commit（呼叫 LLM 前先寫，比照 extractor.py Stage B 的既有時序）
    async with get_async_session() as session:
        execution_id = await AIExecutionRepository(session).start(
            report_id=None, provider=provider_code, model=model,
            symbol=None, market=None, trade_date=None, attempt_no=1,
            prompt_version=PROMPT_VERSION,
            request_meta={"chain_id": chain.chain_id, "stage": "research", "grounded": True},
            view_id=VIEW_ID,
        )
        await session.commit()

    try:
        provider_impl = get_provider(provider_code)
        result = await provider_impl.research_grounded(
            system_prompt, user_prompt, model=model, timeout_sec=timeout_sec,
        )
    except Exception as exc:
        await _record_failure(execution_id, error_code=type(exc).__name__, error_message=str(exc), chain_id=chain.chain_id)
        raise

    # 原始回應先落地（比照 FR-3b 同一個「即使後面用不到也先保留」的精神）
    raw = {
        "chain_id": chain.chain_id, "text": result.text, "citations": result.citations,
        "query_count": result.query_count, "model": result.model,
    }
    snapshot_filename = _save_snapshot(chain.chain_id, raw)

    est_cost = _estimate_cost(model, result.input_tokens, result.output_tokens)
    response_meta = {
        **result.response_meta,
        "grounded": True,
        "query_count": result.query_count,
        "cost_is_partial_estimate": True,
    }
    async with get_async_session() as session:
        await AIExecutionRepository(session).mark_succeeded(
            execution_id, stop_reason=result.stop_reason, response_meta=response_meta,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=None, cache_write_tokens=None,
            image_bytes=None, estimated_cost_usd=est_cost,
            elapsed_ms=result.response_meta.get("elapsed_ms"),
        )
        await ActivityLogRepository(session).log(
            "IC_LLM_RESEARCH_SUCCESS", view_id=VIEW_ID, success=True, rel_id=execution_id,
            detail=f"{chain.chain_id}: {len(result.citations)} 筆引用來源，{result.query_count or 0} 次查詢",
        )
        await session.commit()

    return {
        "text": result.text,
        "citations": result.citations,
        "query_count": result.query_count,
        "snapshot_filename": snapshot_filename,
    }


async def _record_failure(execution_id: int, *, error_code: str, error_message: str, chain_id: str) -> None:
    """收尾寫入吞例外只記警告，比照 extractor.py 同名函式的既有立場：呼叫 LLM 之後的失敗
    不該讓「已經花掉的呼叫沒有紀錄」。"""
    try:
        async with get_async_session() as session:
            await AIExecutionRepository(session).mark_failed(
                execution_id, error_code=error_code[:40], error_message=error_message,
            )
            await ActivityLogRepository(session).log(
                "IC_LLM_RESEARCH_FAILED", view_id=VIEW_ID, success=False, rel_id=execution_id,
                detail=chain_id, comments=f"{error_code}: {error_message}"[:1024],
            )
            await session.commit()
    except Exception:
        logger.exception(f"[產業鏈] {chain_id} Stage A 失敗收尾寫入資料庫時再度失敗（已略過）")
