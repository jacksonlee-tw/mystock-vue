"""警告日誌 SQL Repository 實作"""
import logging

from backend.db.session import COMP_NO, PLANT_NO, OP_USER
from backend.domain.ports.warnlog_repository import WarnlogRepository

log = logging.getLogger(__name__)


class SqlWarnlogRepository(WarnlogRepository):
    """警告日誌 SQL Repository — pyodbc MS SQL Server"""

    def __init__(self, conn):
        self._conn = conn

    def insert_warnlog(self, data: dict) -> bool:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO Warnlog (
                PLANTNO, COMPNO, DBNO, AUFNR, TRUCKNO,
                QTY, LOAD_QTY, CURREENT_QTY, LOG, OP_NAME, OP_TIME
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """,
            PLANT_NO, COMP_NO,
            data.get("dbNo", ""), data.get("aufnr", ""), data.get("truckNo", ""),
            data.get("planQty", 0), data.get("loadQty", 0), data.get("currentQty", 0),
            data.get("log", ""), OP_USER,
        )
        log.info("[WARNLOG] DBNo=%s AUFNR=%s", data.get("dbNo"), data.get("aufnr"))
        return True
