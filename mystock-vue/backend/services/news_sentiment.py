"""
services/news_sentiment.py
新聞情緒批次評分（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §4.1，ADR-P4-08）。

ADR-P4-08（2026-09-13 定案）：Spike-0 以 300 則真實標題驗證 LLM 與人工一致率達 87.0%，
使用者直接拍板不開發本地輕量模型（L1），全部標題一律走 LLM 批次評分——不存在「先本地跑
一輪、極端案例才升級 LLM」的分流，§4.1 原訂的兩層分工表已標註不採用。

呼叫骨架比照 industry_chain/extractor.py：佔位寫入 pending 執行紀錄並 commit（呼叫 LLM 前
先寫，中止也留下紀錄）→ 呼叫 LLM → 依成功/失敗收尾（ai_llm_execution + activity_log）。
與 extractor.py 的差異：這裡一次呼叫夾帶多筆標題（批次結構化輸出），不是「一次呼叫對應一個
實體」，所以 ai_llm_execution 的 symbol/market/trade_date 皆填 None——比照 industry_chain
產業鏈萃取（同樣不對應單一個股）的既有先例，而非強行捏造一個不存在的個股歸屬。

配額：獨立於 AI_DAILY_QUOTA／IC_LLM_MONTHLY_CALL_CAP，用 `NEWS_LLM_DAILY_QUOTA` 搭配
`view_id = "news_sentiment"` 直接查 ai_llm_execution 當日筆數，不另建計數表（同 industry_chain
的 _monthly_call_count() 手法）。ADR-P4-08 後，這個配額限制的語意是「當日批次評分呼叫數」，
不再是文件原訂「當日 L2 升級呼叫數」（見 §4.1 v2.3 更新）。
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import text

from ai import config as ai_config
from ai.providers import get_provider
from config import get_news_llm_daily_quota, get_news_llm_provider
from db.session import get_async_session
from repositories.activity_log_repository import ActivityLogRepository
from repositories.ai_execution_repository import AIExecutionRepository
from repositories.news_repository import NewsRepository
from services.fetcher import FetchStatusManager

logger = logging.getLogger("mystock-backend")

VIEW_ID = "news_sentiment"
PROMPT_VERSION = "v1"
BATCH_SIZE = 30            # 每次 LLM 呼叫夾帶的標題數上限，批次送出降低 per-request overhead（§4.1）
MAX_PENDING_PER_RUN = 300  # 單次觸發最多處理筆數，避免一次補跑歷史積壓把當日配額整批耗盡

sentiment_fetch_status = FetchStatusManager()

# 系統提示內建 Spike-0 人工覆核發現的系統性偏誤修正（見規格書 §15.3-1「設計啟示」）：
# LLM 對「中立」類別的 recall 只有 50.9%，只要標題出現具體正面數字/關鍵字就傾向直接判多，
# 即使人工認為那只是中性的事實揭露；此處明文要求模型對中立類別採保守判準。
SYSTEM_PROMPT = """你是台股新聞標題的多空情緒分類器。任務：判斷每則新聞標題對其提到的個股
近期股價的多空「方向性」影響，而非單純判斷新聞本身「好壞」。

分類為三類之一：
- BULLISH：內容顯示對股價有正面方向性影響（例如營收/獲利優於預期、訂單明顯增加、利多題材成形）
- BEARISH：內容顯示對股價有負面方向性影響（例如營收/獲利衰退、訴訟、財報不如預期、負面事件）
- NEUTRAL：純粹事實揭露、產業/總經統計、活動公告等，不足以判斷方向性

**重要（人工覆核 300 則基準集後發現的系統性偏誤，務必修正）**：不要只因為標題出現具體的正面
數字或關鍵字（例如「營收年增」「訂單」「認證通過」）就直接判多——如果那只是中性的事實陳述、
沒有進一步的方向性語境（例如沒有「創高」「優於預期」「轉機」等強化詞、或只是產業總體統計而非
該公司個股展望），應傾向判為 NEUTRAL。寧可漏判也不要把中性新聞誤判成有方向性訊號，避免產生
假訊號。

score 為 -1.000（極度看空）到 1.000（極度看多）的浮點數，NEUTRAL 應落在 -0.2～0.2 之間。
reason 用一句話說明判斷依據（繁體中文，20 字以內）。"""


class SentimentItem(BaseModel):
    """對應請求中一筆標題的判斷結果。`id` 由我們自己送出的值為準（見 `_build_user_prompt()`），
    模型回傳值只用來比對配對，比照 industry_chain/schema.py「不讓模型有機會創造新 id」的慣例。"""
    id: int
    label: Literal["BULLISH", "NEUTRAL", "BEARISH"]
    score: float = Field(..., ge=-1.0, le=1.0)
    reason: str = ""


class SentimentBatchResult(BaseModel):
    items: list[SentimentItem] = Field(default_factory=list)


def _build_user_prompt(rows: list[dict]) -> str:
    lines = ["請逐則判斷以下台股新聞標題，依 id 對應輸出：", ""]
    lines += [f"[{r['id']}] {r['title']}" for r in rows]
    return "\n".join(lines)


def _estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    pricing = ai_config.get_model_pricing(model)
    if not pricing or input_tokens is None or output_tokens is None:
        return None
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


async def _daily_call_count() -> int:
    async with get_async_session() as session:
        result = await session.execute(
            text("""
                SELECT COUNT(*) FROM ai_llm_execution
                 WHERE view_id = :view_id AND created_at >= CURRENT_DATE
            """),
            {"view_id": VIEW_ID},
        )
        return result.scalar() or 0


async def _score_one_batch(provider_code: str, model: str, rows: list[dict]) -> dict:
    """對一批標題呼叫一次 LLM，寫回 sentiment 欄位並記錄 ai_llm_execution。
    回傳 `{"scored": int, "failed": bool}`——單一批次失敗不中止整輪，呼叫端繼續下一批
    （比照 P1 三來源互相獨立的精神：一批壞了不該拖垮其他批次已經算好的結果）。"""
    user_prompt = _build_user_prompt(rows)

    async with get_async_session() as session:
        execution_id = await AIExecutionRepository(session).start(
            report_id=None, provider=provider_code, model=model,
            symbol=None, market=None, trade_date=None, attempt_no=1,
            prompt_version=PROMPT_VERSION,
            request_meta={"batch_size": len(rows), "news_ids": [r["id"] for r in rows]},
            view_id=VIEW_ID,
        )
        await session.commit()

    try:
        provider_impl = get_provider(provider_code)
        result = await provider_impl.extract_structured(
            SYSTEM_PROMPT, user_prompt, SentimentBatchResult, model=model,
        )
    except Exception as exc:
        async with get_async_session() as session:
            await AIExecutionRepository(session).mark_failed(
                execution_id, error_code=type(exc).__name__, error_message=str(exc)[:500],
            )
            await session.commit()
        logger.error(f"[news_sentiment] 批次評分呼叫失敗: {exc}")
        return {"scored": 0, "failed": True}

    if result.data is None or not result.data.items:
        async with get_async_session() as session:
            await AIExecutionRepository(session).mark_failed(
                execution_id, error_code="NEWS_LLM_NO_PARSED_OUTPUT",
                error_message="LLM 回應無法解析為結構化輸出",
                stop_reason=result.stop_reason, response_meta=result.response_meta,
            )
            await session.commit()
        return {"scored": 0, "failed": True}

    valid_ids = {r["id"] for r in rows}
    scored = 0
    async with get_async_session() as session:
        repo = NewsRepository(session)
        for item in result.data.items:
            if item.id not in valid_ids:
                continue  # 模型自己編出不在請求範圍內的 id，直接忽略、不寫入（比照 IC validator 的防幻覺精神）
            await repo.update_sentiment(item.id, score=item.score, label=item.label, engine="llm")
            scored += 1
        await AIExecutionRepository(session).mark_succeeded(
            execution_id, stop_reason=result.stop_reason, response_meta=result.response_meta,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cache_read_tokens=None, cache_write_tokens=None, image_bytes=None,
            estimated_cost_usd=_estimate_cost(model, result.input_tokens, result.output_tokens),
            elapsed_ms=result.response_meta.get("elapsed_ms"),
        )
        await ActivityLogRepository(session).log(
            "NEWS_SENTIMENT_SCORED", view_id=VIEW_ID, success=True, rel_id=execution_id,
            detail=f"批次 {len(rows)} 則，成功寫入 {scored} 則",
        )
        await session.commit()
    return {"scored": scored, "failed": False}


async def score_pending_news(trigger_type: str = "manual") -> dict:
    """對 `stock_news` 中尚未評分（`sentiment_score IS NULL`）且非重複列的新聞，批次呼叫 LLM
    評分。ADR-P4-08 定案後不存在 L1 本地模型／L2 閘門分流，全部候選一律走這條路徑，直到
    當日配額（`NEWS_LLM_DAILY_QUOTA`）用完為止（AC-P4-07）。"""
    sentiment_fetch_status.start("開始新聞情緒批次評分...")
    provider_code = get_news_llm_provider()
    model = ai_config.get_gemini_model() if provider_code == "gemini" else ai_config.get_claude_model()
    daily_quota = get_news_llm_daily_quota()

    try:
        already_called = await _daily_call_count()
        if already_called >= daily_quota:
            sentiment_fetch_status.complete(f"今日 LLM 呼叫已達配額（{daily_quota}），本次不評分")
            return {"status": "skipped", "reason": "quota_exceeded", "trigger_type": trigger_type}

        async with get_async_session() as session:
            pending = await NewsRepository(session).list_unscored(limit=MAX_PENDING_PER_RUN)

        if not pending:
            sentiment_fetch_status.complete("目前沒有待評分的新聞")
            return {"status": "skipped", "reason": "no_pending", "trigger_type": trigger_type}

        total_scored, total_failed_batches, batches_run = 0, 0, 0
        for i in range(0, len(pending), BATCH_SIZE):
            if already_called + batches_run >= daily_quota:
                break
            batch = pending[i:i + BATCH_SIZE]
            sentiment_fetch_status.update(i, len(pending), f"評分第 {batches_run + 1} 批（{len(batch)} 則）...")
            outcome = await _score_one_batch(provider_code, model, batch)
            batches_run += 1
            total_scored += outcome["scored"]
            total_failed_batches += 1 if outcome["failed"] else 0

        sentiment_fetch_status.complete(f"完成：{batches_run} 批次、寫入 {total_scored} 則、{total_failed_batches} 批次失敗")
        return {
            "status": "completed", "trigger_type": trigger_type,
            "pending_candidates": len(pending), "batches_run": batches_run,
            "scored": total_scored, "failed_batches": total_failed_batches,
        }
    except Exception as e:
        logger.error(f"[news_sentiment] 評分任務失敗: {e}")
        sentiment_fetch_status.fail(str(e))
        raise
