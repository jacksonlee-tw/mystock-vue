"""Dishka IoC 容器設定（Dependency Injection Container）

定義 Provider 類別，宣告各層依賴的建立與生命週期。
Service 層依賴 UnitOfWork（由 Provider 自動注入），不需手動組裝。

Scope 設計：
  - APP:     Engine（應用程式生命週期，單例）
  - REQUEST: UnitOfWork（每次 HTTP Request 一個實例，Request 結束自動清理）
             CardReaderPort（每次 Request 一個實例）
"""
import logging
from collections.abc import Iterator

from dishka import Provider, Scope, provide, make_container

from backend.domain.ports.unit_of_work import UnitOfWork
from backend.infrastructure.uow import SqlUnitOfWork, MemoryUnitOfWork
from backend.infrastructure.memory import MemoryStore, get_default_store
log = logging.getLogger(__name__)


class UoWProvider(Provider):
    """UnitOfWork Provider — 每次 Request 建立一個 UoW，結束時自動清理。

    根據 DB 可用性自動選擇 SqlUnitOfWork 或 MemoryUnitOfWork。
    使用 generator 模式（yield），Dishka 會在 Request 結束時執行 cleanup。
    """
    scope = Scope.REQUEST

    @provide(provides=UnitOfWork)
    def get_uow(self) -> Iterator[UnitOfWork]:
        from backend.db.session import is_fallback, create_connection

        if is_fallback():
            uow = MemoryUnitOfWork()
            yield uow
            return

        conn = create_connection()
        if conn is None:
            uow = MemoryUnitOfWork()
            yield uow
            return

        uow = SqlUnitOfWork(conn)
        try:
            yield uow
        except Exception:
            try:
                uow.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass


def create_container():
    """建立 Dishka 容器（於 main.py 啟動時呼叫）"""
    container = make_container(UoWProvider())
    log.info("✅ Dishka IoC 容器建立完成")
    return container
