"""車輛清單 Repository 介面（Port）"""
from abc import ABC, abstractmethod
from typing import Optional


class TruckRepository(ABC):
    """車輛清單 Repository 抽象介面"""

    @abstractmethod
    def list_trucks(self, keyword: Optional[str] = None) -> list[dict]:
        """查詢車輛清單（排除黑名單車輛）

        Args:
            keyword: 車號關鍵字（模糊搜尋），None 表示回傳全部。

        Returns:
            list of dict { truckNo, lastProdName, lastDbNo, trancomp }。
        """
        ...
