"""pytest 共用 fixtures — 使用 Memory Repository 測試 Service 邏輯

所有 Service 測試透過 MemoryUnitOfWork 運行，不需要 DB 連線。
每個測試函式取得獨立的 MemoryStore 實例，確保測試隔離。
"""
import pytest

from backend.infrastructure.memory import MemoryStore
from backend.infrastructure.uow import MemoryUnitOfWork


@pytest.fixture
def store():
    """獨立的 MemoryStore 實例（各測試不共享狀態）"""
    return MemoryStore()


@pytest.fixture
def uow(store):
    """MemoryUnitOfWork — 封裝 Memory Repository，各測試獨立"""
    return MemoryUnitOfWork(store=store)
