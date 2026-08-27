"""
repositories/activity_log_repository.py
`activity_log` 的唯一 SQL 入口（見 docs/16.AI技術分析/AI技術分析規劃.md §5.6）。
通用事件紀錄表（ADR-AI-18）：本次只接 AI 模組事件（code 以 AI_ 前綴區隔），
命名不加 ai_ 前綴是刻意的，供其他模組日後沿用同一張表與查詢介面。
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mystock-backend")


class ActivityLogRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def log(
        self, code: str, *, view_id: str | None = None, detail: str | None = None,
        success: bool | None = None, rel_id: int | None = None,
        comments: str | None = None, created_by: str = "owner",
    ) -> None:
        await self._s.execute(
            text("""
                INSERT INTO activity_log (code, view_id, detail, success, rel_id, comments, created_by)
                VALUES (:code, :view_id, :detail, :success, :rel_id, :comments, :created_by)
            """),
            {
                "code": code, "view_id": view_id, "detail": detail,
                "success": success, "rel_id": rel_id, "comments": comments,
                "created_by": created_by,
            }
        )

    async def list_logs(
        self, code: str | None = None, rel_id: int | None = None,
        date_from: date | None = None, date_to: date | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[dict], int]:
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if code:
            conditions.append("code = :code")
            params["code"] = code
        if rel_id is not None:
            conditions.append("rel_id = :rel_id")
            params["rel_id"] = rel_id
        if date_from:
            conditions.append("created_date::date >= :date_from")
            params["date_from"] = date_from
        if date_to:
            conditions.append("created_date::date <= :date_to")
            params["date_to"] = date_to

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        result = await self._s.execute(
            text(f"""
                SELECT * FROM activity_log
                {where_clause}
                ORDER BY created_date DESC
                LIMIT :limit OFFSET :offset
            """),
            params
        )
        rows = [dict(r) for r in result.mappings()]

        count_result = await self._s.execute(
            text(f"SELECT COUNT(*) FROM activity_log {where_clause}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")}
        )
        total = count_result.scalar() or 0
        return rows, total

    async def purge_expired(self, retention_days: int) -> int:
        result = await self._s.execute(
            text("""
                DELETE FROM activity_log
                 WHERE created_date < CURRENT_TIMESTAMP - make_interval(days => :days)
            """),
            {"days": retention_days}
        )
        return result.rowcount or 0
