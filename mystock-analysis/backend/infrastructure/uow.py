"""Unit of Work 實作（SQL + Memory）

提供 SqlUnitOfWork 與 MemoryUnitOfWork 兩種實作，
以及 create_uow() 工廠函式根據 DB 可用性自動選擇。

用法：
    from backend.infrastructure.uow import create_uow

    with create_uow() as uow:
        uow.tickets.create_entry(dbno, row)
        uow.commit()
"""
import logging

from backend.domain.ports.unit_of_work import UnitOfWork

# SQL Repositories
from backend.infrastructure.sql.ticket_repository import SqlTicketRepository
from backend.infrastructure.sql.po_repository import SqlPoRepository
from backend.infrastructure.sql.auth_repository import SqlAuthRepository
from backend.infrastructure.sql.truck_repository import SqlTruckRepository
from backend.infrastructure.sql.warnlog_repository import SqlWarnlogRepository
from backend.infrastructure.sql.trace_repository import SqlTraceRepository

# Memory Repositories
from backend.infrastructure.memory import MemoryStore, get_default_store
from backend.infrastructure.memory.ticket_repository import MemoryTicketRepository
from backend.infrastructure.memory.po_repository import MemoryPoRepository
from backend.infrastructure.memory.auth_repository import MemoryAuthRepository
from backend.infrastructure.memory.truck_repository import MemoryTruckRepository
from backend.infrastructure.memory.warnlog_repository import MemoryWarnlogRepository
from backend.infrastructure.memory.trace_repository import MemoryTraceRepository

log = logging.getLogger(__name__)


class SqlUnitOfWork(UnitOfWork):
    """SQL Unit of Work — 封裝 pyodbc 連線與交易控制

    所有 Repository 共用同一條 DB 連線，commit/rollback 統一控制。
    """

    def __init__(self, conn):
        self._conn = conn
        self.tickets = SqlTicketRepository(conn)
        self.po = SqlPoRepository(conn)
        self.auth = SqlAuthRepository(conn)
        self.trucks = SqlTruckRepository(conn)
        self.warnlog = SqlWarnlogRepository(conn)
        self.traces = SqlTraceRepository(conn)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    @property
    def db_mode(self) -> str:
        return "mssql"

    def __enter__(self) -> "SqlUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            try:
                self._conn.rollback()
            except Exception:
                pass
        try:
            self._conn.close()
        except Exception:
            pass


class MemoryUnitOfWork(UnitOfWork):
    """記憶體 Unit of Work — 無交易（commit/rollback 為 no-op）

    所有 Repository 共用同一個 MemoryStore 實例。
    測試時可傳入獨立的 MemoryStore 以實現測試隔離。
    """

    def __init__(self, store: MemoryStore | None = None):
        self._store = store or get_default_store()
        self.tickets = MemoryTicketRepository(self._store)
        self.po = MemoryPoRepository()
        self.auth = MemoryAuthRepository()
        self.trucks = MemoryTruckRepository(self._store)
        self.warnlog = MemoryWarnlogRepository(self._store)
        self.traces = MemoryTraceRepository(self._store)

    def commit(self) -> None:
        pass  # 記憶體模式：寫入即時生效，無需 commit

    def rollback(self) -> None:
        pass  # 記憶體模式：無交易可回滾

    @property
    def db_mode(self) -> str:
        return "memory"

    def __enter__(self) -> "MemoryUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def create_uow(store: MemoryStore | None = None) -> UnitOfWork:
    """建立 Unit of Work 實例

    根據 DB 可用性自動選擇 SQL 或記憶體實作。
    DB 連線失敗時自動降轉為記憶體模式。

    Args:
        store: 可選的 MemoryStore 實例（測試時傳入獨立實例以隔離狀態）。

    Returns:
        UnitOfWork 實例（SqlUnitOfWork 或 MemoryUnitOfWork）。
    """
    from backend.db.session import is_fallback, create_connection

    if is_fallback():
        return MemoryUnitOfWork(store=store)

    conn = create_connection()
    if conn is None:
        return MemoryUnitOfWork(store=store)

    return SqlUnitOfWork(conn)
