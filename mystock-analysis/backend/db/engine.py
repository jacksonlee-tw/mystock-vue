"""SQLAlchemy Core Engine + Connection Pool

提供 SQLAlchemy Engine 工廠，封裝 Connection Pool 設定。
使用 mssql+pyodbc 方言，底層仍由 pyodbc 驅動 MS SQL Server。

Engine 為 Lazy Singleton，首次呼叫 get_engine() 時建立。
Pool 參數可透過環境變數覆寫：
    DB_POOL_SIZE      — 連線池大小（預設 5）
    DB_MAX_OVERFLOW   — 超額連線上限（預設 10）
    DB_POOL_TIMEOUT   — 等待可用連線的秒數（預設 30）
    DB_POOL_RECYCLE   — 連線最大存活秒數（預設 1800）
"""
import logging
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from backend.db.session import DB_SERVER, DB_DATABASE, DB_USER, DB_PASSWORD, DB_DRIVER

log = logging.getLogger(__name__)

# ── Pool 設定（可由環境變數覆寫）──────────────────────────────────────────
POOL_SIZE     = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW  = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT  = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE  = int(os.getenv("DB_POOL_RECYCLE", "1800"))

# ── Lazy Singleton ────────────────────────────────────────────────────────
_engine: Engine | None = None


def _build_connection_url() -> str:
    """組合 SQLAlchemy mssql+pyodbc 連線 URL"""
    driver = quote_plus(DB_DRIVER)
    if DB_USER and DB_PASSWORD:
        user = quote_plus(DB_USER)
        pwd = quote_plus(DB_PASSWORD)
        return (
            f"mssql+pyodbc://{user}:{pwd}@{DB_SERVER}/{DB_DATABASE}"
            f"?driver={driver}&TrustServerCertificate=yes"
        )
    return (
        f"mssql+pyodbc://@{DB_SERVER}/{DB_DATABASE}"
        f"?driver={driver}&Trusted_Connection=yes&TrustServerCertificate=yes"
    )


def get_engine() -> Engine:
    """取得 SQLAlchemy Engine（Lazy Singleton）

    首次呼叫時建立 Engine 並設定 Connection Pool。
    後續呼叫回傳相同實例。
    """
    global _engine
    if _engine is not None:
        return _engine

    url = _build_connection_url()
    _engine = create_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
        pool_pre_ping=True,  # 使用前自動 ping，回收已斷線的連線
    )

    log.info(
        "✅ SQLAlchemy Engine 建立完成 — pool_size=%d, max_overflow=%d, recycle=%ds",
        POOL_SIZE, MAX_OVERFLOW, POOL_RECYCLE,
    )
    return _engine


def dispose_engine() -> None:
    """釋放 Engine 與連線池（應用程式關閉時呼叫）"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
        log.info("🔌 SQLAlchemy Engine 已釋放")
