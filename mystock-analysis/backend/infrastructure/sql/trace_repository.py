"""追蹤記錄 SQL Repository 實作"""
import logging
from datetime import datetime
from typing import Optional

from backend.db.session import OP_USER
from backend.domain.ports.trace_repository import TraceRepository

log = logging.getLogger(__name__)


class SqlTraceRepository(TraceRepository):
    """追蹤記錄 SQL Repository — pyodbc MS SQL Server"""

    def __init__(self, conn):
        self._conn = conn

    def insert_trace(self, data: dict) -> Optional[str]:
        now = datetime.now()
        trace_id = self._next_trace_id()
        hd_date = now.strftime("%Y%m%d")
        hd_time = now.strftime("%H%M%S")

        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO trace_mstr (
                id, inputpoint, dbno, version, pono,
                hddate, hdtime, eventname,
                truckno, supply, prodname,
                A1_WT, A2_WT, B2_WT, B1_WT,
                userno, workflow
            ) VALUES (?, 'A1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            trace_id,
            data.get("dbNo", ""),
            data.get("version", "0"),
            data.get("poNo", ""),
            hd_date, hd_time,
            data.get("eventName", ""),
            data.get("truckNo", ""),
            data.get("supply", ""),
            data.get("prodName", ""),
            data.get("a1Wt", ""),
            data.get("a2Wt", ""),
            data.get("b2Wt", ""),
            data.get("b1Wt", ""),
            data.get("userNo", OP_USER),
            data.get("workFlow", ""),
        )
        log.info("[TRACE] id=%s dbNo=%s event=%s",
                 trace_id, data.get("dbNo"), data.get("eventName"))
        return trace_id

    def _next_trace_id(self) -> str:
        prefix = datetime.now().strftime("%Y%m%d")
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM trace_mstr WHERE id LIKE ?",
            f"{prefix}%",
        )
        row = cur.fetchone()
        seq = (int(row[0]) if row else 0) + 1
        return f"{prefix}{seq:04d}"
