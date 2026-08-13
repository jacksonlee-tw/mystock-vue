"""PostgreSQL 非同步連線管理（asyncpg 驅動，見設計文件第 4.2 節）。"""
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from config import ENV_PATH

load_dotenv(ENV_PATH)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _database_url() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "mystock_db")
    user = os.getenv("POSTGRES_USER", "stock_user")
    password = os.getenv("POSTGRES_PASSWORD", "stock_password")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(_database_url(), pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def dispose_engine() -> None:
    """釋放目前的 asyncpg 連線池。

    asyncpg 的連線繫結在建立時所在的 event loop；同步爬蟲模組透過
    repositories.stock_repository.run_async() 每次呼叫都會開一個新的 asyncio.run()（新的 event loop），
    若沿用舊 loop 建立的連線池會出現 "Event loop is closed"。因此每次同步呼叫結束都呼叫本函式，
    讓下一次呼叫重新建立一份綁定新 loop 的連線池（見設計文件第 4.2 節、repositories/stock_repository.py）。
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
