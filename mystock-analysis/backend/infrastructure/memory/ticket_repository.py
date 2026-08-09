"""磅單記憶體 Repository 實作

實作 TicketRepository 介面，以 MemoryStore 實例取代全域 dict。
"""
import logging
from datetime import datetime
from typing import Optional

from backend.domain.ports.ticket_repository import TicketRepository
from backend.infrastructure.memory import MemoryStore

log = logging.getLogger(__name__)


class MemoryTicketRepository(TicketRepository):
    """磅單記憶體 Repository — 使用 MemoryStore 實例儲存"""

    def __init__(self, store: MemoryStore):
        self._store = store

    def next_dbno(self) -> str:
        today = datetime.now().strftime("%y%m%d")
        with self._store.lock:
            self._store.seq_counter[today] = self._store.seq_counter.get(today, 0) + 1
            return f"{today}{self._store.seq_counter[today]:04d}"

    def create_entry(self, dbno: str, row: dict) -> dict:
        self._store.entry_store[dbno] = row
        log.info("[MEM_CREATE_ENTRY] DBNo=%s TruckNo=%s", dbno, row.get("truckNo"))
        return row

    def get_entry_info(self, dbno: str) -> dict:
        dbno = dbno.strip()
        entry = self._store.entry_store.get(dbno, {})
        return {"a1": int(entry.get("weigth1") or 0), "poNo": str(entry.get("poNo", ""))}

    def update_exit(self, dbno: str, data: dict) -> None:
        now = datetime.now()
        weigth4 = int(data.get("exitWeightB1") or 0)
        is_return = bool(data.get("isReturn", False))
        left_d = data.get("exitDate") or now.strftime("%Y%m%d")
        left_t = data.get("exitTime") or now.strftime("%H%M%S")

        self._store.exit_store[dbno] = {
            **data,
            "weigth4": weigth4,
            "leftDate": left_d,
            "leftTime": left_t,
            "delFlag": is_return,
            "exitAt": now.isoformat(),
        }
        log.info("[MEM_UPDATE_EXIT] DBNo=%s B1=%d Return=%s", dbno, weigth4, is_return)

    def get_ticket(self, dbno: str) -> Optional[dict]:
        dbno = dbno.strip()
        entry = self._store.entry_store.get(dbno)
        if not entry:
            return None
        exit_ = self._store.exit_store.get(dbno, {})
        return self._merge_entry_exit(dbno, entry, exit_)

    def list_today_tickets(self, limit: int = 100) -> list[dict]:
        today_ym = datetime.now().strftime("%y%m%d")
        result = []
        for dbno, entry in self._store.entry_store.items():
            if dbno.startswith(today_ym):
                exit_ = self._store.exit_store.get(dbno, {})
                result.append({
                    "dbNo":     dbno,
                    "truckNo":  entry.get("truckNo", ""),
                    "poNo":     entry.get("poNo", ""),
                    "prodName": entry.get("prodName", ""),
                    "weigth1":  entry.get("weigth1", 0),
                    "weigth4":  exit_.get("weigth4", 0) if exit_ else None,
                    "net":      exit_.get("netWeight", 0) if exit_ else None,
                    "arrDate":  str(entry.get("arrDate", "")),
                    "arrTime":  str(entry.get("arrTime", "")),
                    "delFlag":  bool(exit_.get("delFlag", False)),
                    "status":   "completed" if exit_ else "in_progress",
                })
        return sorted(result, key=lambda x: x["dbNo"], reverse=True)[:limit]

    def update_print_count(self, ticket_no: str, is_entry: bool = True) -> int:
        store = self._store.entry_store if is_entry else self._store.exit_store
        record = store.get(ticket_no)
        if record:
            record["printCount"] = record.get("printCount", 0) + 1
            return record["printCount"]
        return 0

    def add_print_log(self, ticket_no: str, ticket_type: str, found: bool) -> None:
        self._store.print_log.append({
            "ticketNo": ticket_no,
            "type": ticket_type,
            "printAt": datetime.now().isoformat(),
            "found": found,
        })

    # ── 內部輔助 ──────────────────────────────────────────────────────────

    @staticmethod
    def _merge_entry_exit(dbno: str, entry: dict, exit_: dict) -> dict:
        return {
            "dbNo":       dbno,
            "truckNo":    entry.get("truckNo", ""),
            "poNo":       entry.get("poNo", ""),
            "batchNo":    entry.get("batchNo", ""),
            "prodName":   entry.get("prodName", ""),
            "supplier":   entry.get("supply", ""),
            "weigth1":    entry.get("weigth1", 0),
            "weigth4":    exit_.get("weigth4"),
            "net":        exit_.get("netWeight"),
            "arrDate":    str(entry.get("arrDate", "")),
            "arrTime":    str(entry.get("arrTime", "")),
            "leftDate":   str(exit_.get("leftDate", "")),
            "leftTime":   str(exit_.get("leftTime", "")),
            "printNum":   entry.get("printCount", 0),
            "outPrintNum": exit_.get("OutPrintNum", 0),
            "delFlag":    bool(exit_.get("delFlag", False)),
            "status":     "completed" if exit_ else "in_progress",
        }
