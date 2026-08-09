"""磅單 SQL Repository 實作

實作 TicketRepository 介面，透過 pyodbc 操作 MS SQL Server。
所有寫入操作不呼叫 conn.commit()，由 UoW 統一控制交易。
"""
import logging
from datetime import datetime
from typing import Optional

from backend.db.session import COMP_NO, PLANT_NO, OP_USER
from backend.domain.ports.ticket_repository import TicketRepository

log = logging.getLogger(__name__)


class SqlTicketRepository(TicketRepository):
    """磅單 SQL Repository — pyodbc MS SQL Server"""

    def __init__(self, conn):
        self._conn = conn

    def next_dbno(self) -> str:
        today_ymd = datetime.now().strftime("%Y%m%d")
        today_ym = datetime.now().strftime("%y%m%d")
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM CMM_SCALE WHERE ArrDate=? AND compNo=? AND plantNo=?",
            today_ymd, COMP_NO, PLANT_NO,
        )
        row = cur.fetchone()
        seq = (int(row[0]) if row else 0) + 1
        return f"{today_ym}{seq:04d}"

    def create_entry(self, dbno: str, row: dict) -> dict:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO CMM_SCALE (
                compNo, plantNo, DBNo, version,
                TruckNo, PoNo, prodName, supply, SNet, NNet,
                weigth1, ArrDate, ArrTime, workFlow,
                BatchNo, BoatNo, TRANCOMP, WeightMan1, printNum
            ) VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            COMP_NO, PLANT_NO, dbno,
            row["truckNo"], row["poNo"], row["prodName"], row["supply"],
            row.get("sNet"), row.get("nNet"),
            row["weigth1"], row["arrDate"], row["arrTime"], row["workFlow"],
            row["batchNo"], row["boatNo"], row["trancomp"], OP_USER,
        )
        cur.execute(
            "INSERT INTO MMWeighrec (Dbno, WgtNO, WgtValue, CUser) VALUES (?, 'A1', ?, ?)",
            dbno, row["weigth1"], OP_USER,
        )
        if row["poNo"]:
            cur.execute(
                """
                UPDATE MM_POWO_SCALE
                SET    InQty = ISNULL(InQty, 0) + ?
                WHERE  RTRIM(LTRIM(AUFNR)) = ?
                """,
                row["weigth1"], row["poNo"],
            )
        log.info("[CREATE_ENTRY] DBNo=%s TruckNo=%s A1=%s", dbno, row["truckNo"], row["weigth1"])
        return row

    def get_entry_info(self, dbno: str) -> dict:
        dbno = dbno.strip()
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT ISNULL(weigth1, 0), ISNULL(PoNo, '')
            FROM   CMM_SCALE
            WHERE  DBNo    = ?
              AND  version = (SELECT MAX(version) FROM CMM_SCALE WHERE DBNo = ?)
            """,
            dbno, dbno,
        )
        row = cur.fetchone()
        if row:
            return {"a1": int(row[0]), "poNo": str(row[1])}
        return {"a1": 0, "poNo": ""}

    def update_exit(self, dbno: str, data: dict) -> None:
        now       = datetime.now()
        left_d    = data.get("exitDate") or now.strftime("%Y%m%d")
        left_t    = data.get("exitTime") or now.strftime("%H%M%S")
        weigth4   = int(data.get("exitWeightB1") or 0)
        is_return = bool(data.get("isReturn", False))
        net       = data.get("netWeight", 0)
        a1        = data.get("a1", 0)
        po_no     = data.get("poNo", "")

        cur = self._conn.cursor()

        if is_return:
            cur.execute(
                """
                UPDATE CMM_SCALE SET
                    DelFlag=1, DelReason=N'退貨',
                    weigth4=weigth1, weigth2=weigth1, weigth3=weigth1,
                    TTare=CAST(weigth1 AS VARCHAR(10)),
                    Net=0, outStoreTime=GETDATE(),
                    LeftDate=?, LeftTime=?, weightman4=?
                WHERE  DBNo    = ?
                  AND  version = (SELECT MAX(version) FROM CMM_SCALE WHERE DBNo = ?)
                """,
                left_d, left_t, OP_USER, dbno, dbno,
            )
            if po_no and a1 > 0:
                cur.execute(
                    """
                    UPDATE MM_POWO_SCALE
                    SET    InQty = ISNULL(InQty, 0) - ?
                    WHERE  RTRIM(LTRIM(AUFNR)) = ?
                      AND  ISNULL(InQty, 0) - ? >= 0
                    """,
                    a1, po_no, a1,
                )
        else:
            r_truck   = str(data.get("corrCarNo", "") or "").strip()
            r_po      = str(data.get("corrPoNo", "") or "").strip()
            r_prod    = str(data.get("corrMaterialName", "") or "").strip()
            r_supply  = str(data.get("corrSupplierName", "") or "").strip()
            r_snet    = int(data.get("corrNetWeightSupplier") or 0) or None
            r_nnet    = int(data.get("corrNetWeightNotary") or 0) or None
            weigth2   = int(data.get("storageWeightA2") or 0) or None
            weigth3   = int(data.get("outboundWeightB2") or 0) or None
            ab_flag   = "Y" if data.get("exitStatus") == "warning" else None

            cur.execute(
                """
                UPDATE CMM_SCALE SET
                    weigth4=?, Net=?, TTare=CAST(? AS VARCHAR(10)),
                    LeftDate=?, LeftTime=?, weightman4=?,
                    RTruckNo=?, RPoNo=?, RprodName=?, RSupply=?,
                    RSNet=?, RNNet=?,
                    weigth2=COALESCE(?, weigth2),
                    weigth3=COALESCE(?, weigth3),
                    abFlag=?, DelFlag=0,
                    outStoreTime=GETDATE(),
                    OutPrintNum=0
                WHERE  DBNo    = ?
                  AND  version = (SELECT MAX(version) FROM CMM_SCALE WHERE DBNo = ?)
                """,
                weigth4, net, weigth4,
                left_d, left_t, OP_USER,
                r_truck, r_po, r_prod, r_supply,
                r_snet, r_nnet,
                weigth2, weigth3,
                ab_flag,
                dbno, dbno,
            )
            if po_no and a1 > 0:
                cur.execute(
                    """
                    UPDATE MM_POWO_SCALE
                    SET    InQty = ISNULL(InQty, 0) - ? + ?
                    WHERE  RTRIM(LTRIM(AUFNR)) = ?
                      AND  ISNULL(InQty, 0) - ? + ? >= 0
                    """,
                    a1, net, po_no, a1, net,
                )

        cur.execute(
            "INSERT INTO MMWeighrec (Dbno, WgtNO, WgtValue, CUser) VALUES (?, 'B1', ?, ?)",
            dbno, weigth4, OP_USER,
        )
        log.info("[UPDATE_EXIT] DBNo=%s B1=%d Net=%d Return=%s", dbno, weigth4, net, is_return)

    def get_ticket(self, dbno: str) -> Optional[dict]:
        dbno = dbno.strip()
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT DBNo,
                   ISNULL(TruckNo,''),  ISNULL(PoNo,''),
                   ISNULL(prodName,''), ISNULL(supply,''),
                   ISNULL(SNet,0),      ISNULL(NNet,0),
                   ISNULL(weigth1,0),   ISNULL(weigth2,0),
                   ISNULL(weigth3,0),   ISNULL(weigth4,0),
                   ISNULL(Net,0),
                   ISNULL(ArrDate,''),  ISNULL(ArrTime,''),
                   ISNULL(LeftDate,''), ISNULL(LeftTime,''),
                   ISNULL(abFlag,''),   ISNULL(BatchNo,''),
                   ISNULL(BoatNo,''),   ISNULL(TRANCOMP,''),
                   ISNULL(workFlow,''),
                   ISNULL(printNum,0),  ISNULL(OutPrintNum,0),
                   ISNULL(DelFlag,0),
                   ISNULL(RTruckNo,''), ISNULL(RPoNo,''),
                   ISNULL(RprodName,N''), ISNULL(RSupply,N'')
            FROM   CMM_SCALE
            WHERE  DBNo    = ?
              AND  version = (SELECT MAX(version) FROM CMM_SCALE WHERE DBNo = ?)
            """,
            dbno, dbno,
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_flat(row)

    def list_today_tickets(self, limit: int = 100) -> list[dict]:
        today = datetime.now().strftime("%Y%m%d")
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT TOP(?) CMM.DBNo,
                   ISNULL(CMM.TruckNo,''), ISNULL(CMM.PoNo,''),
                   ISNULL(CMM.prodName,''),
                   ISNULL(CMM.weigth1,0),  ISNULL(CMM.weigth4,0),
                   ISNULL(CMM.Net,0),
                   ISNULL(CMM.ArrDate,''), ISNULL(CMM.ArrTime,''),
                   ISNULL(CMM.DelFlag,0)
            FROM   CMM_SCALE CMM
            WHERE  CMM.ArrDate = ?
              AND  CMM.compNo  = ?
              AND  CMM.plantNo = ?
              AND  CMM.version = (
                  SELECT MAX(v2.version) FROM CMM_SCALE v2 WHERE v2.DBNo = CMM.DBNo
              )
            ORDER BY CMM.DBNo DESC
            """,
            limit, today, COMP_NO, PLANT_NO,
        )
        rows = cur.fetchall()
        return [
            {
                "dbNo": r[0], "truckNo": r[1], "poNo": r[2],
                "prodName": r[3], "weigth1": r[4],
                "weigth4": r[5] if r[5] else None,
                "net": r[6] if r[6] else None,
                "arrDate": r[7], "arrTime": r[8],
                "delFlag": bool(r[9]),
                "status": "completed" if (r[5] and r[5] > 0) else "in_progress",
            }
            for r in rows
        ]

    def update_print_count(self, ticket_no: str, is_entry: bool = True) -> int:
        field = "printNum" if is_entry else "OutPrintNum"
        cur = self._conn.cursor()
        cur.execute(
            f"""
            UPDATE CMM_SCALE SET {field} = ISNULL({field}, 0) + 1
            WHERE  DBNo    = ?
              AND  version = (SELECT MAX(version) FROM CMM_SCALE WHERE DBNo = ?)
            """,
            ticket_no, ticket_no,
        )
        cur.execute(
            f"""
            SELECT ISNULL({field}, 0) FROM CMM_SCALE
            WHERE  DBNo    = ?
              AND  version = (SELECT MAX(version) FROM CMM_SCALE WHERE DBNo = ?)
            """,
            ticket_no, ticket_no,
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def add_print_log(self, ticket_no: str, ticket_type: str, found: bool) -> None:
        # 列印日誌目前僅記錄於記憶體（尚無對應 DB 資料表）
        pass

    # ── 內部輔助 ──────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_flat(row) -> dict:
        return {
            "dbNo":       row[0],
            "truckNo":    row[1],
            "poNo":       row[2],
            "prodName":   row[3],
            "supplier":   row[4],
            "sNet":       row[5],
            "nNet":       row[6],
            "weigth1":    row[7],
            "weigth2":    row[8] if row[8] else None,
            "weigth3":    row[9] if row[9] else None,
            "weigth4":    row[10] if row[10] else None,
            "net":        row[11] if row[11] else None,
            "arrDate":    row[12],
            "arrTime":    row[13],
            "leftDate":   row[14],
            "leftTime":   row[15],
            "abFlag":     row[16],
            "batchNo":    row[17],
            "boatNo":     row[18],
            "trancomp":   row[19],
            "workFlow":   row[20],
            "printNum":   row[21],
            "outPrintNum": row[22],
            "delFlag":    bool(row[23]),
            "rTruckNo":   row[24],
            "rPoNo":      row[25],
            "rProdName":  row[26],
            "rSupply":    row[27],
            "status":     "completed" if (row[10] and row[10] > 0) else "in_progress",
        }
