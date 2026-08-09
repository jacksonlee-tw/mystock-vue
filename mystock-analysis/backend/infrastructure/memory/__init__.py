"""記憶體儲存（MemoryStore）

封裝所有 Mock 資料為 class 實例，消除模組級全域狀態。
每個 MemoryStore 實例持有獨立的資料集合，支援：
  - 測試隔離：各測試案例建立獨立 store，不互相汙染
  - 共享實例：生產記憶體模式使用 get_default_store() 取得共享實例
"""
import threading


class MemoryStore:
    """記憶體儲存容器 — 封裝所有 Mock 資料

    取代舊有模組級全域 dict，將資料封裝為實例屬性。
    """

    def __init__(self):
        self.lock = threading.Lock()

        # 磅單存儲
        self.entry_store: dict[str, dict] = {}
        self.exit_store: dict[str, dict] = {}
        self.print_log: list[dict] = []
        self.seq_counter: dict[str, int] = {}

        # 警告日誌
        self.warnlog_store: list[dict] = []

        # 追蹤記錄
        self.trace_store: list[dict] = []
        self.trace_seq: dict[str, int] = {}


# ── 預設共享實例（生產記憶體模式使用）────────────────────────────────────
_default_store: MemoryStore | None = None
_store_lock = threading.Lock()


def get_default_store() -> MemoryStore:
    """取得預設共享 MemoryStore 實例（Lazy Singleton）"""
    global _default_store
    if _default_store is None:
        with _store_lock:
            if _default_store is None:
                _default_store = MemoryStore()
    return _default_store
