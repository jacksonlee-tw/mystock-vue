"""車輛清單記憶體 Repository 實作"""
from typing import Optional

from backend.domain.ports.truck_repository import TruckRepository
from backend.infrastructure.memory import MemoryStore


class MemoryTruckRepository(TruckRepository):
    """車輛清單記憶體 Repository — 從 MemoryStore.entry_store 取得車輛資料"""

    def __init__(self, store: MemoryStore):
        self._store = store

    def list_trucks(self, keyword: Optional[str] = None) -> list[dict]:
        trucks = []
        seen: set[str] = set()
        for dbno, entry in self._store.entry_store.items():
            truck_no = entry.get("truckNo", "")
            if truck_no and truck_no not in seen:
                if keyword and keyword.upper() not in truck_no.upper():
                    continue
                seen.add(truck_no)
                trucks.append({
                    "truckNo": truck_no,
                    "lastProdName": entry.get("prodName", ""),
                    "lastDbNo": dbno,
                    "trancomp": entry.get("trancomp", ""),
                })
        return sorted(trucks, key=lambda x: x["lastDbNo"], reverse=True)
