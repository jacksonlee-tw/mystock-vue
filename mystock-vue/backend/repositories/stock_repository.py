"""唯一的資料存取入口；API 層與排程都只透過它操作資料庫，不直接寫 SQL（見 ERD/UML 文件第 2 節）。"""
import asyncio
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from db.models import CrawlerLog, DailyStockData, MarketNoTradingDay, Symbol, SymbolIndustry
from db.session import _database_url, get_session_factory


_bg_engine: AsyncEngine | None = None
_bg_session_factory: async_sessionmaker | None = None


def _get_bg_session_factory() -> async_sessionmaker:
    global _bg_engine, _bg_session_factory
    if _bg_session_factory is None:
        _bg_engine = create_async_engine(_database_url(), pool_pre_ping=True)
        _bg_session_factory = async_sessionmaker(_bg_engine, expire_on_commit=False)
    return _bg_session_factory


async def _dispose_bg_engine() -> None:
    global _bg_engine, _bg_session_factory
    if _bg_engine is not None:
        await _bg_engine.dispose()
    _bg_engine = None
    _bg_session_factory = None


class _BackgroundSessionFactory:
    def __call__(self):
        return _get_bg_session_factory()()


def run_async(coro):
    """讓同步的爬蟲模組（fetcher.py / us_fetcher.py）可以呼叫 async 版的 Repository 方法。

    每次呼叫都是獨立的 asyncio.run()（新的 event loop），且只釋放背景同步橋接專用的連線池，
    不影響 FastAPI 主 event loop 正在使用的 db/session.py 全域連線池。
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
            await _dispose_bg_engine()

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

    async def get_symbol_summaries(self, market_type: str) -> list[dict]:
        """批次取得某市場所有「有歷史資料」symbol 的摘要（最新日期、最新收盤價、公司名稱、記錄筆數），
        一次 SQL 查完（DISTINCT ON + window function）。

        用途是取代 services/stock_service.py discover_available_stocks() 原本「對每個 symbol 各呼叫一次
        get_daily_data()」的寫法：symbols 表在個股產業標籤同步（services/industry_fetcher.py）後會被灌入
        整個市場的代碼（TW 兩千多檔），但真正有 daily_stock_data 的往往只有追蹤中的幾十檔，逐檔查詢等於
        上千次序列 DB round trip，實測會讓 /api/v1/stocks 逾時（15s 都不夠）。這裡改成單一查詢，且因為
        是從 daily_stock_data 出發（INNER JOIN symbols），本來就只會回傳「真的有資料」的 symbol。

        額外排除 `security_type == 'index'`（大盤指數功能規劃書 ADR-I3：指數不得混進個股清單/下拉選單）——
        指數與類股指數資料透過 db/dual_write.py 寫進同一張 daily_stock_data（ADR-I1「指數即標的」），
        FK-ensure 會在 symbols 表留下對應列，不過濾的話會冒出來當成股票（見 TWSE_S15 等類股代號那次修復）。"""
        async with self._session_factory() as session:
            stmt = (
                select(
                    DailyStockData.symbol,
                    DailyStockData.trade_date,
                    DailyStockData.close_price,
                    Symbol.name,
                    func.count().over(partition_by=DailyStockData.symbol).label("total_records"),
                )
                .join(Symbol, Symbol.symbol == DailyStockData.symbol)
                .where(
                    DailyStockData.market_type == market_type,
                    or_(Symbol.security_type.is_(None), Symbol.security_type != "index"),
                )
                .distinct(DailyStockData.symbol)
                .order_by(DailyStockData.symbol, DailyStockData.trade_date.desc())
            )
            result = await session.execute(stmt)
            return [
                {
                    "symbol": row.symbol,
                    "name": row.name,
                    "latest_date": row.trade_date,
                    "latest_close": float(row.close_price) if row.close_price is not None else 0.0,
                    "total_records": row.total_records,
                }
                for row in result.all()
            ]

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

    async def get_symbols(self, codes: list[str], market_type: str) -> list[dict]:
        """精確多筆查詢（IN），給 markets/tw.py 的 validate_symbols() 做批次驗證用。"""
        if not codes:
            return []
        async with self._session_factory() as session:
            stmt = select(Symbol).where(Symbol.market_type == market_type, Symbol.symbol.in_(codes))
            result = await session.execute(stmt)
            return [_symbol_to_dict(row) for row in result.scalars().all()]

    async def search_symbols(self, query: str, market_type: str, limit: int = 20) -> list[dict]:
        """代號前綴或名稱模糊搜尋，給自動完成用（見 markets/tw.py 的 search_symbols()）。
        代號完全相等的排最前面，其餘依代號排序。"""
        q = query.strip()
        if not q:
            return []
        async with self._session_factory() as session:
            stmt = (
                select(Symbol)
                .where(
                    Symbol.market_type == market_type,
                    Symbol.is_active.is_(True),
                    or_(Symbol.symbol.ilike(f"{q}%"), Symbol.name.ilike(f"%{q}%")),
                )
                .order_by((Symbol.symbol == q).desc(), Symbol.symbol.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_symbol_to_dict(row) for row in result.scalars().all()]

    async def list_symbols_page(
        self,
        market_type: str,
        query: Optional[str] = None,
        industry_code: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """全市場代碼主檔的分頁瀏覽／篩選（見 stocks.py 的 GET /stocks/symbols）。跟 search_symbols()
        分工：這裡要準確的 total 筆數（做分頁）與可選的產業別篩選（LEFT JOIN symbol_industry），
        search_symbols() 只要「前 N 筆建議」給自動完成用，不需要 total 也不需要產業別。"""
        conditions = [Symbol.market_type == market_type]
        q = (query or "").strip()
        if q:
            conditions.append(or_(Symbol.symbol.ilike(f"{q}%"), Symbol.name.ilike(f"%{q}%")))
        if industry_code:
            conditions.append(SymbolIndustry.industry_code == industry_code)

        async with self._session_factory() as session:
            count_stmt = (
                select(func.count(Symbol.symbol))
                .select_from(Symbol)
                .outerjoin(SymbolIndustry, SymbolIndustry.symbol == Symbol.symbol)
                .where(*conditions)
            )
            total = (await session.execute(count_stmt)).scalar_one()

            list_stmt = (
                select(Symbol, SymbolIndustry.industry_code, SymbolIndustry.industry_name)
                .outerjoin(SymbolIndustry, SymbolIndustry.symbol == Symbol.symbol)
                .where(*conditions)
                .order_by(Symbol.symbol.asc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(list_stmt)
            items = [
                {
                    **_symbol_to_dict(row.Symbol),
                    "industry_code": row.industry_code,
                    "industry_name": row.industry_name,
                }
                for row in result.all()
            ]
        return items, total

    async def list_distinct_industries(self, market_type: str) -> list[dict]:
        """給篩選下拉選單用的產業別選項：只回傳主檔裡實際有資料的分類，不會出現篩了卻 0 筆的選項。"""
        async with self._session_factory() as session:
            stmt = (
                select(SymbolIndustry.industry_code, SymbolIndustry.industry_name)
                .where(SymbolIndustry.market_type == market_type)
                .distinct()
                .order_by(SymbolIndustry.industry_code.asc())
            )
            result = await session.execute(stmt)
            return [{"industry_code": r.industry_code, "industry_name": r.industry_name} for r in result.all()]

    # asyncpg 單一陳述式的 query 參數上限是 32767；本表一列 6 欄，美股 SEC 清單單次就上萬列，
    # 遠超這個上限會直接丟 InterfaceError（見 services/symbol_master_fetcher.py 的呼叫端），
    # 所以要分批送出。500 列/批 = 3000 參數，遠低於上限，也讓單一陳述式不會太肥。
    _UPSERT_SYMBOLS_BATCH_SIZE = 500

    async def upsert_symbols_bulk(self, rows: list[dict]) -> int:
        """rows: [{"symbol", "market_type", "name", "exchange", "status"}, ...]。
        用於 services/symbol_master_fetcher.py 的全市場代碼清單同步：只更新 market_type/name/
        exchange/status，刻意不動 security_type，避免蓋掉 upsert_symbol()（例如
        scripts/import_json_to_postgres.py）已經填好的值。"""
        if not rows:
            return 0
        async with self._session_factory() as session:
            for i in range(0, len(rows), self._UPSERT_SYMBOLS_BATCH_SIZE):
                batch = rows[i:i + self._UPSERT_SYMBOLS_BATCH_SIZE]
                stmt = pg_insert(Symbol).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Symbol.symbol],
                    set_={
                        "market_type": stmt.excluded.market_type,
                        "name": stmt.excluded.name,
                        "exchange": stmt.excluded.exchange,
                        "status": stmt.excluded.status,
                    },
                )
                await session.execute(stmt)
            await session.commit()
        return len(rows)

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

    async def upsert_daily_data(self, rows: list[dict], security_type: Optional[str] = None) -> None:
        """rows 需符合 db/mapping.py 的 record_to_daily_row() 輸出格式；
        ON CONFLICT 需覆蓋全部欄位，否則新舊資料會混在同一列（見設計文件第 4.1 節風險）。

        `security_type`：FK-ensure 新建 symbols 列時要打的分類（例如指數傳 `'index'`，見
        大盤指數功能規劃書 ADR-I3）。只在「新建」該列時寫入，既有列一律不覆蓋——代碼主檔同步
        （services/industry_fetcher.py 等）才是個股 security_type 的權威來源。"""
        if not rows:
            return

        async with self._session_factory() as session:
            # daily_stock_data.symbol 有 FK 依賴，先確保 symbols 表已有對應列（不覆蓋既有資料）
            symbol_seen: dict[str, str] = {}
            for row in rows:
                symbol_seen.setdefault(row["symbol"], row["market_type"])
            sym_stmt = pg_insert(Symbol).values(
                [{"symbol": s, "market_type": m, "security_type": security_type} for s, m in symbol_seen.items()]
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

    # ── symbol_industry（個股產業標籤，見大盤指數功能規劃書 §8.2）─────────
    async def upsert_symbol_industry(self, rows: list[dict]) -> None:
        """rows: [{"symbol", "market_type", "industry_code", "industry_name"}, ...]。
        比照 upsert_daily_data()：先確保 symbols 表有對應列（FK 依賴），industry_fetcher.py
        可能獨立於價格爬蟲執行，不能假設 symbols 一定已存在。"""
        if not rows:
            return
        async with self._session_factory() as session:
            symbol_seen: dict[str, str] = {}
            for row in rows:
                symbol_seen.setdefault(row["symbol"], row["market_type"])
            sym_stmt = pg_insert(Symbol).values(
                [{"symbol": s, "market_type": m} for s, m in symbol_seen.items()]
            )
            sym_stmt = sym_stmt.on_conflict_do_nothing(index_elements=[Symbol.symbol])
            await session.execute(sym_stmt)

            stmt = pg_insert(SymbolIndustry).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[SymbolIndustry.symbol],
                set_={
                    "market_type": stmt.excluded.market_type,
                    "industry_code": stmt.excluded.industry_code,
                    "industry_name": stmt.excluded.industry_name,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def list_symbol_industries(self, market_type: Optional[str] = None) -> list[dict]:
        async with self._session_factory() as session:
            stmt = select(SymbolIndustry)
            if market_type:
                stmt = stmt.where(SymbolIndustry.market_type == market_type)
            result = await session.execute(stmt)
            return [
                {
                    "symbol": r.symbol, "market_type": r.market_type,
                    "industry_code": r.industry_code, "industry_name": r.industry_name,
                }
                for r in result.scalars().all()
            ]

    # ── 給同步爬蟲模組使用的橋接方法（見 db/dual_write.py） ──────────────
    def upsert_daily_data_sync(self, rows: list[dict], security_type: Optional[str] = None) -> None:
        run_async(self.upsert_daily_data(rows, security_type=security_type))

    def log_crawler_run_sync(self, **kwargs: Any) -> None:
        run_async(self.log_crawler_run(**kwargs))

    def add_no_trading_days_sync(self, market_type: str, dates, source: str = "probed") -> None:
        run_async(self.add_no_trading_days(market_type, dates, source))

    def upsert_symbol_industry_sync(self, rows: list[dict]) -> None:
        run_async(self.upsert_symbol_industry(rows))

    # get_symbols()／search_symbols()／upsert_symbols_bulk() 沒有 _sync 橋接：它們只從
    # markets/tw.py／us.py（FastAPI 主 event loop 內）與 services/symbol_master_fetcher.py
    # （BackgroundTasks，同樣在主 loop 內）呼叫，必須直接 await，不能用 run_async()（見該函式
    # 的說明——在還有其他併發請求共用同一個 db/session.py 全域 engine 時呼叫 run_async()／
    # dispose_engine() 會把它們的連線一併弄壞）。
