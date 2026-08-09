"""採購單 Repository 介面（Port）"""
from abc import ABC, abstractmethod
from typing import Optional


class PoRepository(ABC):
    """採購單 Repository 抽象介面"""

    @abstractmethod
    def get_po_info(self, po_no: str) -> Optional[dict]:
        """查詢採購單資料（原料名稱、供應商、計畫量、已用量）"""
        ...
