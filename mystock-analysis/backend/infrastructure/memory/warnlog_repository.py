"""警告日誌記憶體 Repository 實作"""
import logging
from datetime import datetime

from backend.domain.ports.warnlog_repository import WarnlogRepository
from backend.infrastructure.memory import MemoryStore

log = logging.getLogger(__name__)


class MemoryWarnlogRepository(WarnlogRepository):
    """警告日誌記憶體 Repository"""

    def __init__(self, store: MemoryStore):
        self._store = store

    def insert_warnlog(self, data: dict) -> bool:
        self._store.warnlog_store.append({**data, "opTime": datetime.now().isoformat()})
        log.info("[WARNLOG] 記憶體模式：%s", data.get("log", ""))
        return True
