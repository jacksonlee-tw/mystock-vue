"""
repositories/ai_execution_repository.py
`ai_llm_execution` 的唯一 SQL 入口（見 docs/16.AI技術分析/AI技術分析規劃.md §5.5）。
成本與 token 統計的唯一事實來源（ADR-AI-17）——粒度是「每一次呼叫」，成功與失敗一視同仁。
"""
from __future__ import annotations
import json
import logging
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mystock-backend")


class AIExecutionRepository(object):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def start(
        self, *, report_id: int | None, provider: str, model: str,
        symbol: str, market: str, trade_date: date, attempt_no: int,
        prompt_version: str, request_meta: dict, is_dry_run: bool = False,
        submitted_by: str = "owner", call_mode: str = "blocking",
        view_id: str | None = None,
    ) -> int:
        """呼叫 LLM **之前**先寫入 pending 列（§5.7 關鍵約束：先寫再呼叫，
        否則行程在呼叫途中被中止就完全沒有紀錄）。回傳新列 id。

        view_id：觸發功能來源（見 docs/16.AI技術分析/執行歷史頁面開發計劃.md §2.1 與 V18 migration）。"""
        result = await self._s.execute(
            text("""
                INSERT INTO ai_llm_execution
                       (report_id, provider, model, call_mode, prompt_version,
                        symbol, market_type, trade_date, status, attempt_no,
                        request_meta, is_dry_run, submitted_by, view_id, started_at)
                VALUES (:report_id, :provider, :model, :call_mode, :prompt_version,
                        :symbol, :market, :trade_date, 'pending', :attempt_no,
                        :request_meta, :is_dry_run, :submitted_by, :view_id, CURRENT_TIMESTAMP)
                RETURNING id
            """),
            {
                "report_id": report_id, "provider": provider, "model": model,
                "call_mode": call_mode, "prompt_version": prompt_version,
                "symbol": symbol, "market": market, "trade_date": trade_date,
                "attempt_no": attempt_no, "request_meta": json.dumps(request_meta),
                "is_dry_run": is_dry_run, "submitted_by": submitted_by, "view_id": view_id,
            }
        )
        await self._s.flush()
        return result.scalar()

    async def mark_succeeded(
        self, execution_id: int, *, stop_reason: str | None,
        response_meta: dict, provider_request_id: str | None,
        input_tokens: int | None, output_tokens: int | None,
        cache_read_tokens: int | None, cache_write_tokens: int | None,
        image_bytes: int | None, estimated_cost_usd: float | None, elapsed_ms: int | None,
    ) -> None:
        await self._s.execute(
            text("""
                UPDATE ai_llm_execution
                   SET status              = 'succeeded',
                       stop_reason         = :stop_reason,
                       response_meta       = :response_meta,
                       provider_request_id = :provider_request_id,
                       input_tokens        = :input_tokens,
                       output_tokens       = :output_tokens,
                       cache_read_tokens   = :cache_read_tokens,
                       cache_write_tokens  = :cache_write_tokens,
                       image_bytes         = :image_bytes,
                       estimated_cost_usd  = :estimated_cost_usd,
                       elapsed_ms          = :elapsed_ms,
                       completed_at        = CURRENT_TIMESTAMP,
                       updated_at          = CURRENT_TIMESTAMP
                 WHERE id = :id
            """),
            {
                "id": execution_id, "stop_reason": stop_reason,
                "response_meta": json.dumps(response_meta),
                "provider_request_id": provider_request_id,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "cache_read_tokens": cache_read_tokens, "cache_write_tokens": cache_write_tokens,
                "image_bytes": image_bytes, "estimated_cost_usd": estimated_cost_usd,
                "elapsed_ms": elapsed_ms,
            }
        )

    async def mark_failed(
        self, execution_id: int, *, error_code: str, error_message: str,
        elapsed_ms: int | None = None,
        input_tokens: int | None = None, output_tokens: int | None = None,
    ) -> None:
        """失敗同樣可能已計費（例如已開始生成才逾時），token 欄位允許填入已知部分用量。"""
        await self._s.execute(
            text("""
                UPDATE ai_llm_execution
                   SET status         = 'failed',
                       error_code     = :error_code,
                       error_message  = :error_message,
                       elapsed_ms     = :elapsed_ms,
                       input_tokens   = COALESCE(:input_tokens, input_tokens),
                       output_tokens  = COALESCE(:output_tokens, output_tokens),
                       completed_at   = CURRENT_TIMESTAMP,
                       updated_at     = CURRENT_TIMESTAMP
                 WHERE id = :id
            """),
            {
                "id": execution_id, "error_code": error_code, "error_message": error_message,
                "elapsed_ms": elapsed_ms, "input_tokens": input_tokens, "output_tokens": output_tokens,
            }
        )

    # ── 查詢（§6.3）─────────────────────────────────────────────
        async def get_latest_succeeded_for_report(self, report_id: int) -> dict | None:
                result = await self._s.execute(
                        text("""
                                SELECT provider, model, prompt_version, completed_at
                                    FROM ai_llm_execution
                                 WHERE report_id = :report_id
                                     AND status = 'succeeded'
                                 ORDER BY completed_at DESC NULLS LAST, id DESC
                                 LIMIT 1
                        """),
                        {"report_id": report_id},
                )
                row = result.mappings().first()
                return dict(row) if row else None

    async def list_executions(
        self, provider: str | None = None, model: str | None = None,
        status: str | None = None, symbol: str | None = None, market: str | None = None,
        date_from: date | None = None, date_to: date | None = None,
        include_dry_run: bool = False, view_id: str | None = None,
        limit: int = 20, offset: int = 0,
    ) -> tuple[list[dict], int]:
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if not include_dry_run:
            conditions.append("is_dry_run = FALSE")
        if view_id:
            conditions.append("view_id = :view_id")
            params["view_id"] = view_id
        if provider:
            conditions.append("provider = :provider")
            params["provider"] = provider
        if model:
            conditions.append("model = :model")
            params["model"] = model
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if symbol:
            conditions.append("symbol = :symbol")
            params["symbol"] = symbol
        if market:
            conditions.append("market_type = :market")
            params["market"] = market
        if date_from:
            conditions.append("created_at::date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("created_at::date <= :date_to")
            params["date_to"] = date_to

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        result = await self._s.execute(
            text(f"""
                SELECT id, execution_uuid, report_id, provider, model, call_mode, prompt_version,
                       symbol, market_type, trade_date, status, attempt_no, stop_reason,
                       error_code, error_message, provider_request_id, view_id,
                       request_meta, response_meta,
                       input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                       total_tokens, image_bytes, estimated_cost_usd, elapsed_ms,
                       started_at, completed_at, is_dry_run, submitted_by, created_at
                  FROM ai_llm_execution
                  {where_clause}
                 ORDER BY created_at DESC
                 LIMIT :limit OFFSET :offset
            """),
            params
        )
        # request_meta／response_meta 是 JSONB，僅中繼資料（§8.2 不含 prompt 全文與圖片），
        # 資料量小，列表頁一併帶出即可，不需要另開一支單筆詳情端點。
        rows = [dict(r) for r in result.mappings()]

        count_result = await self._s.execute(
            text(f"SELECT COUNT(*) FROM ai_llm_execution {where_clause}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")}
        )
        total = count_result.scalar() or 0
        return rows, total

    async def get_usage_totals(
        self, date_from: date | None = None, date_to: date | None = None,
    ) -> dict:
        """用量與成本彙總（§6.3 GET /ai/usage 的 totals 區塊）。"""
        conditions = ["is_dry_run = FALSE"]
        params: dict[str, Any] = {}
        if date_from:
            conditions.append("created_at::date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("created_at::date <= :date_to")
            params["date_to"] = date_to
        where_clause = f"WHERE {' AND '.join(conditions)}"

        result = await self._s.execute(
            text(f"""
                SELECT
                    COUNT(*)                                              AS call_count,
                    COUNT(*) FILTER (WHERE status = 'succeeded')          AS success_count,
                    COUNT(*) FILTER (WHERE status = 'failed')             AS failed_count,
                    COALESCE(SUM(input_tokens), 0)                        AS input_tokens,
                    COALESCE(SUM(output_tokens), 0)                       AS output_tokens,
                    COALESCE(SUM(total_tokens), 0)                        AS total_tokens,
                    COALESCE(SUM(estimated_cost_usd), 0)                  AS estimated_cost_usd
                  FROM ai_llm_execution
                  {where_clause}
            """),
            params
        )
        row = result.mappings().first()
        return dict(row) if row else {
            "call_count": 0, "success_count": 0, "failed_count": 0,
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0,
        }

    async def get_usage_by_group(
        self, group_by: str, date_from: date | None = None, date_to: date | None = None,
    ) -> list[dict]:
        """group_by: 'model' | 'symbol' | 'day'（依 created_at::date 分組）。"""
        column_map = {"model": "model", "symbol": "symbol", "day": "created_at::date"}
        group_col = column_map.get(group_by, "model")

        conditions = ["is_dry_run = FALSE"]
        params: dict[str, Any] = {}
        if date_from:
            conditions.append("created_at::date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("created_at::date <= :date_to")
            params["date_to"] = date_to
        where_clause = f"WHERE {' AND '.join(conditions)}"

        result = await self._s.execute(
            text(f"""
                SELECT {group_col} AS key,
                       COUNT(*) AS call_count,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd
                  FROM ai_llm_execution
                  {where_clause}
                 GROUP BY {group_col}
                 ORDER BY estimated_cost_usd DESC
            """),
            params
        )
        return [dict(r) for r in result.mappings()]

    async def purge_expired(self, retention_days: int) -> int:
        result = await self._s.execute(
            text("""
                DELETE FROM ai_llm_execution
                 WHERE created_at < CURRENT_TIMESTAMP - make_interval(days => :days)
            """),
            {"days": retention_days}
        )
        return result.rowcount or 0

    async def count_by_report(self, report_id: int) -> int:
        """該報告目前已有幾次呼叫紀錄，供 guard.py 計算下一次的 attempt_no。"""
        result = await self._s.execute(
            text("SELECT COUNT(*) FROM ai_llm_execution WHERE report_id = :report_id"),
            {"report_id": report_id}
        )
        return result.scalar() or 0
