"""Unit of Work 介面（Port）

定義交易邊界抽象，Service 層透過 UoW 控制 commit/rollback，
不直接操作資料庫連線。

UoW 同時作為 Repository 容器，提供各領域的 Repository 實例。
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.ticket_repository import TicketRepository
    from backend.domain.ports.po_repository import PoRepository
    from backend.domain.ports.auth_repository import AuthRepository
    from backend.domain.ports.truck_repository import TruckRepository
    from backend.domain.ports.warnlog_repository import WarnlogRepository
    from backend.domain.ports.trace_repository import TraceRepository


class UnitOfWork(ABC):
    """Unit of Work 抽象介面

    管理交易邊界（commit/rollback），並作為 Repository 容器。
    Service 層透過 UoW 存取各 Repository，於業務操作完成後呼叫 commit()。

    用法：
        with create_uow() as uow:
            uow.tickets.create_entry(dbno, row)
            uow.commit()
    """
    tickets: "TicketRepository"
    po: "PoRepository"
    auth: "AuthRepository"
    trucks: "TruckRepository"
    warnlog: "WarnlogRepository"
    traces: "TraceRepository"

    @abstractmethod
    def commit(self) -> None:
        """提交交易"""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """回滾交易"""
        ...

    @property
    @abstractmethod
    def db_mode(self) -> str:
        """回傳目前資料庫模式（'mssql' 或 'memory'）"""
        ...

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        ...

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...
