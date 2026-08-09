"""追蹤記錄記憶體 Repository 實作"""
import logging
from datetime import datetime
from typing import Optional

from backend.domain.ports.trace_repository import TraceRepository
from backend.infrastructure.memory import MemoryStore

log = logging.getLogger(__name__)


class MemoryTraceRepository(TraceRepository):
    """追蹤記錄記憶體 Repository"""

    def __init__(self, store: MemoryStore):
        self._store = store

    def insert_trace(self, data: dict) -> Optional[str]:
        now = datetime.now()
        prefix = now.strftime("%Y%m%d")
        with self._store.lock:
            self._store.trace_seq[prefix] = self._store.trace_seq.get(prefix, 0) + 1
            trace_id = f"{prefix}{self._store.trace_seq[prefix]:04d}"

        hd_date = now.strftime("%Y%m%d")
        hd_time = now.strftime("%H%M%S")
        self._store.trace_store.append({
            "id": trace_id, **data,
            "hdDate": hd_date, "hdTime": hd_time,
        })
        log.info("[TRACE] 記憶體模式：id=%s dbNo=%s", trace_id, data.get("dbNo", ""))
        return trace_id
