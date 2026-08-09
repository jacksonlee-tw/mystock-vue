"""採購單 SQL Repository 實作"""
import logging
from typing import Optional

from backend.domain.ports.po_repository import PoRepository
from backend.infrastructure.memory.po_repository import MemoryPoRepository

log = logging.getLogger(__name__)


class SqlPoRepository(PoRepository):
    """採購單 SQL Repository — pyodbc MS SQL Server"""

    def __init__(self, conn):
        self._conn = conn
        self._fallback = MemoryPoRepository()

    def get_po_info(self, po_no: str) -> Optional[dict]:
        po_no = po_no.strip()
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT RTRIM(LTRIM(AUFNR)),
                       RTRIM(LTRIM(ISNULL(MAKTX,''))),
                       RTRIM(LTRIM(ISNULL(NAME1,''))),
                       ISNULL(MENGE,0), ISNULL(InQty,0), ISNULL(closed,0)
                FROM   MM_POWO_SCALE
                WHERE  RTRIM(LTRIM(AUFNR)) = ?
                """,
                po_no,
            )
            row = cur.fetchone()
            if row:
                plan_qty = float(row[3])
                used_qty = float(row[4])
                return {
                    "poNo":         row[0],
                    "materialName": row[1],
                    "supplier":     row[2],
                    "planQty":      plan_qty,
                    "usedQty":      used_qty,
                    "ratio":        used_qty / plan_qty if plan_qty > 0 else 0.0,
                    "closed":       bool(row[5]),
                }
        except Exception as exc:
            log.warning("get_po_info DB 失敗，降轉 Mock：%s", exc)
            return self._fallback.get_po_info(po_no)
        # DB 查無資料時，嘗試回退 Mock（POC 階段相容）
        return self._fallback.get_po_info(po_no)
