"""採購單記憶體 Repository 實作"""
import logging
from typing import Optional

from backend.domain.ports.po_repository import PoRepository

log = logging.getLogger(__name__)

# ── Mock 採購單資料 ──────────────────────────────────────────────────────
_MOCK_PO: dict[str, dict] = {
    "PO001": {"materialName": "砂石料",  "supplier": "台灣砂石有限公司",  "planQty": 50000.0,  "usedQty": 35000.0},
    "PO002": {"materialName": "水泥",    "supplier": "台泥股份有限公司",  "planQty": 100000.0, "usedQty": 88000.0},
    "PO003": {"materialName": "鋼筋",    "supplier": "中鋼公司",          "planQty": 20000.0,  "usedQty": 21000.0},
    "PO004": {"materialName": "碎石子",  "supplier": "大成建材有限公司",  "planQty": 30000.0,  "usedQty": 12000.0},
}


class MemoryPoRepository(PoRepository):
    """採購單記憶體 Repository"""

    def get_po_info(self, po_no: str) -> Optional[dict]:
        po_no = po_no.strip()
        po = _MOCK_PO.get(po_no.upper()) or _MOCK_PO.get(po_no)
        if po:
            ratio = po["usedQty"] / po["planQty"] if po["planQty"] > 0 else 0.0
            return {**po, "poNo": po_no, "ratio": ratio, "closed": False}
        return None
