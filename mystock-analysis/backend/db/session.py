"""資料庫連線與 Session 管理（pyodbc — MS SQL Server）。

使用 Context Manager (`get_db_context()`) 管理連線，避免 Depends() 死鎖。
若 DB 不可用（pyodbc 未安裝或連線失敗），自動切換為記憶體 Mock 模式。

用法：
    from backend.db.session import get_db_context

    with get_db_context() as conn:
        # conn 為 pyodbc.Connection 或 None（記憶體模式）
        ...
"""
import os
import logging
from contextlib import contextmanager

log = logging.getLogger(__name__)

# ── DB 連線設定（由 .env 或環境變數覆寫）─────────────────────────────────
DB_SERVER   = os.getenv("DB_SERVER",   "192.168.153.12")
DB_DATABASE = os.getenv("DB_DATABASE", "openSQLDB")
DB_USER     = os.getenv("DB_USER",     "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DRIVER   = os.getenv("DB_DRIVER",   "ODBC Driver 18 for SQL Server")
COMP_NO     = os.getenv("COMP_NO",     "MM01")
PLANT_NO    = os.getenv("PLANT_NO",    "PL01")
OP_USER     = os.getenv("OP_USER",     "SYS")

# ── 模式切換旗標 ──────────────────────────────────────────────────────────
_fallback: bool = False


def _conn_str() -> str:
    """組合 pyodbc 連線字串"""
    if DB_USER and DB_PASSWORD:
        return (
            f"DRIVER={{{DB_DRIVER}}};"
            f"SERVER={DB_SERVER};DATABASE={DB_DATABASE};"
            f"UID={DB_USER};PWD={DB_PASSWORD};"
            f"TrustServerCertificate=yes;"
        )
    return (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};DATABASE={DB_DATABASE};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )


def check_availability() -> bool:
    """啟動時測試 DB 連線。回傳 True 表示 DB 可用。"""
    global _fallback
    try:
        import pyodbc  # noqa: F401
        conn = pyodbc.connect(_conn_str(), timeout=5)
        conn.close()
        _fallback = False
        log.info("✅ DB 連線成功 → %s / %s  (COMP=%s PLANT=%s)",
                 DB_SERVER, DB_DATABASE, COMP_NO, PLANT_NO)
        return True
    except ImportError:
        _fallback = True
        log.warning("⚠️  pyodbc 未安裝，使用記憶體 Mock 模式")
    except Exception as exc:
        _fallback = True
        log.warning("⚠️  DB 連線失敗，使用記憶體 Mock 模式：%s", exc)
    return False


def is_fallback() -> bool:
    """回傳目前是否為記憶體 Mock 模式"""
    return _fallback


def create_connection():
    """建立 pyodbc 連線（透過 SQLAlchemy Connection Pool）。

    fallback 或連線失敗時回傳 None。
    供 UnitOfWork 工廠使用，不含 Context Manager 包裝。
    回傳的是 pyodbc raw connection，由 SQLAlchemy Pool 管理生命週期。
    """
    if _fallback:
        return None
    try:
        from backend.db.engine import get_engine
        engine = get_engine()
        return engine.raw_connection()
    except Exception as exc:
        log.warning("create_connection 連線失敗（SQLAlchemy Pool）：%s", exc)
        # 降級：直接使用 pyodbc 建立連線
        try:
            import pyodbc
            return pyodbc.connect(_conn_str(), timeout=5)
        except Exception:
            return None


@contextmanager
def get_db_context():
    """
    Context Manager 管理 DB 連線，避免 Depends() 死鎖。
    fallback 模式下 yield None，CRUD 層可依此切換記憶體操作。

    注意：連線錯誤處理與 yield 分開，確保 AppException 在 with 區塊內
    拋出時能正常向上傳遞，不被此處的 except 誤捕。
    """
    if _fallback:
        yield None
        return

    conn = None
    try:
        import pyodbc
        conn = pyodbc.connect(_conn_str(), timeout=5)
    except Exception as exc:
        log.warning("get_db_context 連線失敗，降轉記憶體：%s", exc)
        yield None
        return

    try:
        yield conn
    finally:
        conn.close()
