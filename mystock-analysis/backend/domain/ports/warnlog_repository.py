"""警告日誌 Repository 介面（Port）"""
from abc import ABC, abstractmethod


class WarnlogRepository(ABC):
    """警告日誌 Repository 抽象介面"""

    @abstractmethod
    def insert_warnlog(self, data: dict) -> bool:
        """寫入採購量警示日誌

        Args:
            data: 欄位字典（dbNo, aufnr, truckNo, planQty, loadQty, currentQty, log）。

        Returns:
            True 表示寫入成功。
        """
        ...
