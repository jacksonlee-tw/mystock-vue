"""唯一的資料存取入口；API 層與排程都只透過它操作資料庫，不直接寫 SQL（見 ERD/UML 文件第 2 節）。"""
import asyncio
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import CrawlerLog, DailyStockData, MarketNoTradingDay, Symbol
from db.session import get_session_factory


def run_async(coro):
    """讓同步的爬蟲模組（fetcher.py / us_fetcher.py）可以呼叫 async 版的 Repository 方法。

    每次呼叫都是獨立的 asyncio.run()（新的 event loop），結束後主動釋放連線池，
    避免下一次呼叫沿用綁定在舊 loop 的 asyncpg 連線而炸掉（見 db/session.py 的 dispose_engine()）。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("run_async() 不可在既有的事件迴圈中呼叫，請直接 await 對應的 async 方法")

    async def _runner():
        try:
            return await coro
        finally:
            from db.session import dispose_engine
            await dispose_engine()

    return asyncio.run(_runner())


def _symbol_to_dict(row: Symbol) -> dict:
    return {
        "symbol": row.symbol,
        "market_type": row.market_type,
        "name": row.name,
        "exchange": row.exchange,
        "security_type": row.security_type,
        "status": row.status,
        "is_active": row.is_active,
        "created_at": row.created_at,
    }


def _daily_to_dict(row: DailyStockData) -> dict:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "market_type": row.market_type,
        "trade_date": row.trade_date,
        "open_price": row.open_price,
        "high_price": row.high_price,
        "low_price": row.low_price,
        "close_price": row.close_price,
        "volume": row.volume,
        "turnover": row.turnover,
        "transaction_count": row.transaction_count,
        "market_specific_data": row.market_specific_data,
    }


def _log_to_dict(row: CrawlerLog) -> dict:
    return {
        "id": row.id,
        "market_type": row.market_type,
        "trigger_type": row.trigger_type,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "status": row.status,
        "symbols_success": row.symbols_success,
        "symbols_failed": row.symbols_failed,
        "error_message": row.error_message,
    }


class StockRepository:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory or get_session_factory()

    # ── symbols ───────────────────────────────────────────────────────
    async def get_symbol(self, symbol: str) -> Optional[dict]:
        async with self._session_factory() as session:
            row = await session.get(Symbol, symbol)
            return _symbol_to_dict(row) if row else None

    async def list_symbols(self, market_type: Optional[str] = None) -> list[dict]:
        async with self._session_factory() as session:
            stmt = select(Symbol)
            if market_type:
                stmt = stmt.where(Symbol.market_type == market_type)
            result = await session.execute(stmt.order_by(Symbol.symbol))
            return [_symbol_to_dict(row) for row in result.scalars().all()]

    async def upsert_symbol(
        self,
        symbol: str,
        market_type: str,
        name: Optional[str] = None,
        exchange: Optional[str] = None,
        security_type: Optional[str] = None,
        status: str = "active",
    ) -> None:
        async with self._session_factory() as session:
            stmt = pg_insert(Symbol).values(
                symbol=symbol,
                market_type=market_type,
                name=name,
                exchange=exchange,
                security_type=security_type,
                status=status,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Symbol.symbol],
                set_={
                    "market_type": stmt.excluded.market_type,
                    "name": stmt.excluded.name,
                    "exchange": stmt.excluded.exchange,
                    "security_type": stmt.excluded.security_type,
                    "status": stmt.excluded.status,
                },
            )
            await session.execute(stmt)
            await session.commit()

    # ── daily_stock_data ──────────────────────────────────────────────
    async def get_daily_data(
        self, symbol: str, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> list[dict]:
        async with self._session_factory() as session:
            stmt = select(DailyStockData).where(DailyStockData.symbol == symbol)
            if date_from:
                stmt = stmt.where(DailyStockData.trade_date >= date_from)
            if date_to:
                stmt = stmt.where(DailyStockData.trade_date <= date_to)
            result = await session.execute(stmt.order_by(DailyStockData.trade_date))
            return [_daily_to_dict(row) for row in result.scalars().all()]

    async def upsert_daily_data(self, rows: list[dict]) -> None:
        """rows 需符合 db/mapping.py 的 record_to_daily_row() 輸出格式；
        ON CONFLICT 需覆蓋全部欄位，否則新舊資料會混在同一列（見設計文件第 4.1 節風險）。"""
        if not rows:
            return

        async with self._session_factory() as session:
            # daily_stock_data.symbol 有 FK 依賴，先確保 symbols 表已有對應列（不覆蓋既有資料）
            symbol_seen: dict[str, str] = {}
            for row in rows:
                symbol_seen.setdefault(row["symbol"], row["market_type"])
            sym_stmt = pg_insert(Symbol).values(
                [{"symbol": s, "market_type": m} for s, m in symbol_seen.items()]
            )
            sym_stmt = sym_stmt.on_conflict_do_nothing(index_elements=[Symbol.symbol])
            await session.execute(sym_stmt)

            stmt = pg_insert(DailyStockData).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[DailyStockData.symbol, DailyStockData.trade_date],
                set_={
                    "open_price": stmt.excluded.open_price,
                    "high_price": stmt.excluded.high_price,
                    "low_price": stmt.excluded.low_price,
                    "close_price": stmt.excluded.close_price,
                    "volume": stmt.excluded.volume,
                    "turnover": stmt.excluded.turnover,
                    "transaction_count": stmt.excluded.transaction_count,
                    "market_specific_data": stmt.excluded.market_specific_data,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
            await session.commit()

    # ── crawler_logs ──────────────────────────────────────────────────
    async def log_crawler_run(
        self,
        market_type: str,
        trigger_type: str,
        started_at: datetime,
        status: str,
        finished_at: Optional[datetime] = None,
        symbols_success: int = 0,
        symbols_failed: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                CrawlerLog(
                    market_type=market_type,
                    trigger_type=trigger_type,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=status,
                    symbols_success=symbols_success,
                    symbols_failed=symbols_failed,
                    error_message=error_message,
                )
            )
            await session.commit()

    async def get_latest_success(self, market_type: str) -> Optional[dict]:
        async with self._session_factory() as session:
            stmt = (
                select(CrawlerLog)
                .where(CrawlerLog.market_type == market_type, CrawlerLog.status == "success")
                .order_by(CrawlerLog.started_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            return _log_to_dict(row) if row else None

    # ── market_no_trading_days（見 phase3_5 設計文件第 3.5 節） ──────────
    async def get_no_trading_days(self, market_type: str) -> set:
        async with self._session_factory() as session:
            stmt = select(MarketNoTradingDay.trade_date).where(MarketNoTradingDay.market_type == market_type)
            result = await session.execute(stmt)
            return set(result.scalars().all())

    async def add_no_trading_days(self, market_type: str, dates, source: str = "probed") -> None:
        if not dates:
            return
        async with self._session_factory() as session:
            stmt = pg_insert(MarketNoTradingDay).values(
                [{"market_type": market_type, "trade_date": d, "source": source} for d in dates]
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=[MarketNoTradingDay.market_type, MarketNoTradingDay.trade_date]
            )
            await session.execute(stmt)
            await session.commit()

    # ── 給同步爬蟲模組使用的橋接方法（見 db/dual_write.py） ──────────────
    def upsert_daily_data_sync(self, rows: list[dict]) -> None:
        run_async(self.upsert_daily_data(rows))

    def log_crawler_run_sync(self, **kwargs: Any) -> None:
        run_async(self.log_crawler_run(**kwargs))

    def add_no_trading_days_sync(self, market_type: str, dates, source: str = "probed") -> None:
        run_async(self.add_no_trading_days(market_type, dates, source))
