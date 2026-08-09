"""磅單 Repository 介面（Port）

定義磅單資料存取的抽象合約，Service 層依賴此介面而非具體實作。
"""
from abc import ABC, abstractmethod
from typing import Optional


class TicketRepository(ABC):
    """磅單 Repository 抽象介面"""

    @abstractmethod
    def next_dbno(self) -> str:
        """產生當日流水磅單號（格式：YYMMDDNNNN）"""
        ...

    @abstractmethod
    def create_entry(self, dbno: str, row: dict) -> dict:
        """插入入廠記錄（CMM_SCALE + MMWeighrec A1 + MM_POWO_SCALE.InQty）"""
        ...

    @abstractmethod
    def get_entry_info(self, dbno: str) -> dict:
        """取得入廠記錄基本資訊（A1 重量與採購單號），供出廠計算淨重"""
        ...

    @abstractmethod
    def update_exit(self, dbno: str, data: dict) -> None:
        """更新出廠欄位（CMM_SCALE + MMWeighrec B1 + MM_POWO_SCALE.InQty）"""
        ...

    @abstractmethod
    def get_ticket(self, dbno: str) -> Optional[dict]:
        """查詢磅單記錄（單筆，最新版本）"""
        ...

    @abstractmethod
    def list_today_tickets(self, limit: int = 100) -> list[dict]:
        """查詢當日所有磅單"""
        ...

    @abstractmethod
    def update_print_count(self, ticket_no: str, is_entry: bool = True) -> int:
        """遞增列印次數，回傳新計數"""
        ...

    @abstractmethod
    def add_print_log(self, ticket_no: str, ticket_type: str, found: bool) -> None:
        """新增列印日誌"""
        ...
