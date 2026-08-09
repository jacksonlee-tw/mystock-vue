"""車輛清單 SQL Repository 實作"""
import logging
from typing import Optional

from backend.db.session import COMP_NO, PLANT_NO
from backend.domain.ports.truck_repository import TruckRepository

log = logging.getLogger(__name__)


class SqlTruckRepository(TruckRepository):
    """車輛清單 SQL Repository — pyodbc MS SQL Server"""

    def __init__(self, conn):
        self._conn = conn

    def list_trucks(self, keyword: Optional[str] = None) -> list[dict]:
        try:
            cur = self._conn.cursor()
            sql = """
                SELECT truckno, PRODNAME, dbno, TRANCOMP FROM (
                    SELECT c.truckno, b.trancomp, a.dbno, a.PRODNAME
                    FROM (SELECT DISTINCT truckno FROM CMM_SCALE) c
                    LEFT JOIN TruckList b ON c.TruckNo = b.TruckNo
                    LEFT JOIN CMM_SCALE a ON a.truckno = c.TRUCKNO
                        AND a.dbno = (SELECT MAX(e.DBNo) FROM CMM_SCALE e WHERE TruckNo = a.TRUCKNO)
                ) x
                WHERE ISNULL(TruckNo,'') <> ''
                  AND TRUCKNO NOT IN (SELECT TruckNo FROM TruckList WHERE IsBlack = 1)
            """
            params = []
            if keyword:
                sql += " AND TruckNo LIKE ?"
                params.append(f"%{keyword}%")
            sql += " ORDER BY DBNo DESC"
            cur.execute(sql, *params)
            rows = cur.fetchall()
            return [
                {
                    "truckNo":      row[0].strip() if row[0] else "",
                    "lastProdName": row[1].strip() if row[1] else "",
                    "lastDbNo":     row[2].strip() if row[2] else "",
                    "trancomp":     row[3].strip() if row[3] else "",
                }
                for row in rows
            ]
        except Exception as exc:
            log.warning("list_trucks DB 失敗：%s", exc)
            return []
