"""追蹤記錄 Repository 介面（Port）"""
from abc import ABC, abstractmethod
from typing import Optional


class TraceRepository(ABC):
    """追蹤記錄 Repository 抽象介面"""

    @abstractmethod
    def insert_trace(self, data: dict) -> Optional[str]:
        """寫入操作稽核追蹤記錄

        Args:
            data: 欄位字典（dbNo, version, poNo, eventName, ...）。

        Returns:
            新產生的 12 碼 trace ID 字串。
        """
        ...
