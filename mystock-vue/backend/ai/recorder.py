"""
ai/recorder.py
執行紀錄（ai_llm_execution）與事件紀錄（activity_log）的統一寫入門面（見規格書 §5.7）。

寫入時機依 §5.7 的時序：
  guard.resolve_report_slot() 取得執行權
  → start_execution()（呼叫 LLM **之前**，pending）
  → 呼叫 LLM
  → record_success() / record_failure()（連同 ai_analysis_report 一併更新）
  → log_event()

規則：呼叫 LLM 前的 start_execution() 若失敗直接向上拋（尚未花錢，中止比帶病繼續安全）；
呼叫 LLM **之後**的收尾寫入（record_success/record_failure/log_event）一律吞例外只記日誌，
不得讓已經花錢取得的報告因為寫 log 失敗而回傳錯誤給使用者（§4.7 共同規範、AC-AI-28）。
"""
from __future__ import annotations
import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.ai_report_repository import AIReportRepository
from repositories.ai_execution_repository import AIExecutionRepository
from repositories.activity_log_repository import ActivityLogRepository

logger = logging.getLogger("mystock-backend")


class AIRecorder:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._report_repo = AIReportRepository(session)
        self._exec_repo = AIExecutionRepository(session)
        self._log_repo = ActivityLogRepository(session)

    async def start_execution(
        self, *, report_id: int, provider: str, model: str, symbol: str, market: str,
        trade_date: date, attempt_no: int, prompt_version: str, request_meta: dict,
        is_dry_run: bool = False, view_id: str | None = None,
    ) -> int:
        """呼叫 LLM 之前的佔位寫入。刻意不吞例外：這一步失敗代表還沒送出請求、還沒花錢，
        中止比繼續呼叫卻沒有紀錄安全（§5.7 關鍵約束）。

        view_id：這次呼叫是哪個功能觸發的（執行歷史頁面「功能」欄位，見規格書外的
        docs/16.AI技術分析/執行歷史頁面開發計劃.md §2.1）。呼叫端本來就知道自己是哪個 view——
        呼叫其餘 log_* 方法時已經在傳這個字串，這裡補齊讓 ai_llm_execution 也記得住。"""
        return await self._exec_repo.start(
            report_id=report_id, provider=provider, model=model,
            symbol=symbol, market=market, trade_date=trade_date, attempt_no=attempt_no,
            prompt_version=prompt_version, request_meta=request_meta, is_dry_run=is_dry_run,
            view_id=view_id,
        )

    async def record_success(
        self, *, execution_id: int, report_id: int, view_id: str | None,
        stop_reason: str | None, response_meta: dict, provider_request_id: str | None,
        input_tokens: int | None, output_tokens: int | None,
        cache_read_tokens: int | None, cache_write_tokens: int | None,
        image_bytes: int | None, estimated_cost_usd: float | None, elapsed_ms: int | None,
        report_data: dict,
    ) -> None:
        """成功收尾：更新執行紀錄 + 報告內容 + 事件紀錄，同一個 session（交易）內完成。
        寫入失敗只記日誌，不向上拋（使用者已經拿到報告，不可因此收到錯誤）。"""
        try:
            await self._exec_repo.mark_succeeded(
                execution_id, stop_reason=stop_reason, response_meta=response_meta,
                provider_request_id=provider_request_id,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens, cache_write_tokens=cache_write_tokens,
                image_bytes=image_bytes, estimated_cost_usd=estimated_cost_usd, elapsed_ms=elapsed_ms,
            )
            await self._report_repo.mark_succeeded(report_id, report_data)
            await self._log_repo.log(
                "AI_REPORT_GENERATE", view_id=view_id, success=True, rel_id=report_id,
                detail=f"{report_data.get('provider')}/{report_data.get('model')} 產生成功",
            )
        except Exception:
            logger.exception("[AI] 報告 id=%s 成功後的紀錄寫入失敗（已略過，報告仍正常回傳）", report_id)

    async def record_failure(
        self, *, execution_id: int | None, report_id: int, view_id: str | None,
        error_code: str, error_message: str, elapsed_ms: int | None = None,
        input_tokens: int | None = None, output_tokens: int | None = None,
    ) -> None:
        """失敗收尾：即使呼叫 LLM 失敗，執行紀錄與報告狀態仍必須更新，
        否則該標的當日會被殭屍 running 列永久卡住（§4.7 共同規範）。"""
        try:
            if execution_id is not None:
                await self._exec_repo.mark_failed(
                    execution_id, error_code=error_code, error_message=error_message,
                    elapsed_ms=elapsed_ms, input_tokens=input_tokens, output_tokens=output_tokens,
                )
            await self._report_repo.mark_failed(report_id, error_code)
            await self._log_repo.log(
                "AI_REPORT_GENERATE", view_id=view_id, success=False, rel_id=report_id,
                comments=f"{error_code}: {error_message}"[:1024],
            )
        except Exception:
            logger.exception("[AI] 報告 id=%s 失敗後的紀錄寫入失敗（已略過）", report_id)

    async def log_cached(self, *, view_id: str | None, report_id: int) -> None:
        try:
            await self._log_repo.log("AI_REPORT_CACHED", view_id=view_id, success=True, rel_id=report_id)
        except Exception:
            logger.exception("[AI] AI_REPORT_CACHED 事件寫入失敗（已略過）")

    async def log_blocked(self, *, view_id: str | None, comments: str) -> None:
        try:
            await self._log_repo.log("AI_REPORT_BLOCKED", view_id=view_id, success=False, comments=comments)
        except Exception:
            logger.exception("[AI] AI_REPORT_BLOCKED 事件寫入失敗（已略過）")

    async def log_view(self, *, view_id: str | None, report_id: int) -> None:
        try:
            await self._log_repo.log("AI_REPORT_VIEW", view_id=view_id, success=True, rel_id=report_id)
        except Exception:
            logger.exception("[AI] AI_REPORT_VIEW 事件寫入失敗（已略過）")

    async def log_query(self, *, view_id: str | None, comments: str) -> None:
        try:
            await self._log_repo.log("AI_REPORT_QUERY", view_id=view_id, success=True, comments=comments)
        except Exception:
            logger.exception("[AI] AI_REPORT_QUERY 事件寫入失敗（已略過）")

    async def log_delete(self, *, view_id: str | None, report_id: int, success: bool) -> None:
        try:
            await self._log_repo.log("AI_REPORT_DELETE", view_id=view_id, success=success, rel_id=report_id)
        except Exception:
            logger.exception("[AI] AI_REPORT_DELETE 事件寫入失敗（已略過）")
