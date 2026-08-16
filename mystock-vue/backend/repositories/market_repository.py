"""全市場日資料與作業存取 Repository（選股功能與爬蟲 規格書 §3.4、§8.4、ADR-SP-11、ADR-SP-14）。

四張全市場新表 (daily_market_quote / daily_market_chip / daily_valuation / monthly_revenue)
與作業表 (market_fetch_job) 的唯一 SQL 存取層。
"""
import asyncio
from datetime import date, datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from db.models import (
    DailyMarketChip,
    DailyMarketQuote,
    DailyValuation,
    MarketFetchJob,
    MarketNoTradingDay,
    MonthlyRevenue,
    Symbol,
    SymbolIndustry,
)
from db.session import get_session_factory

logger = logging.getLogger("mystock-backend")


class ActiveFetchJobError(Exception):
    """已有 status='running' 的 market_fetch_job 存在（由 V10 的部分唯一索引在 DB 層擋下，
    取代無法跨 run_async() 呼叫存活的 session 級 pg_advisory_lock，見 ADR-SP-14 後續修正）。"""

SORT_COLUMN_WHITELIST = {
    "symbol": DailyMarketQuote.symbol,
    "close": DailyMarketQuote.close_price,
    "close_price": DailyMarketQuote.close_price,
    "change_percent": DailyMarketQuote.change_percent,
    "volume": DailyMarketQuote.volume,
    "turnover": DailyMarketQuote.turnover,
    "pe_ratio": DailyValuation.pe_ratio,
    "pb_ratio": DailyValuation.pb_ratio,
    "dividend_yield": DailyValuation.dividend_yield,
    "market_cap": DailyValuation.market_cap,
    "mcap_rank": DailyValuation.mcap_rank,
    "foreign_net": DailyMarketChip.foreign_net,
    "trust_net": DailyMarketChip.trust_net,
    "dealer_net": DailyMarketChip.dealer_net,
    "institutional_net": DailyMarketChip.institutional_net,
    "margin_balance": DailyMarketChip.margin_balance,
    "short_balance": DailyMarketChip.short_balance,
}


def run_async(coro):
    """讓同步的爬蟲模組可以呼叫 async 版的 Repository 方法。"""
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


class MarketRepository:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory or get_session_factory()

    # ── 1. UPSERT 行情資料 ─────────────────────────────────────────────
    async def upsert_quotes(self, records: List[Dict[str, Any]]) -> int:
        """整批 UPSERT 全市場行情，單日交易（§3.9.3）。
        來源欄位為空時保留舊值，不得將已存在的非空值覆寫為 NULL（§3.7）。
        """
        if not records:
            return 0
        async with self._session_factory() as session:
            async with session.begin():
                stmt = pg_insert(DailyMarketQuote).values(records)
                update_dict = {
                    "open_price": func.coalesce(stmt.excluded.open_price, DailyMarketQuote.open_price),
                    "high_price": func.coalesce(stmt.excluded.high_price, DailyMarketQuote.high_price),
                    "low_price": func.coalesce(stmt.excluded.low_price, DailyMarketQuote.low_price),
                    "close_price": func.coalesce(stmt.excluded.close_price, DailyMarketQuote.close_price),
                    "change_amount": func.coalesce(stmt.excluded.change_amount, DailyMarketQuote.change_amount),
                    "change_percent": func.coalesce(stmt.excluded.change_percent, DailyMarketQuote.change_percent),
                    "volume": func.coalesce(stmt.excluded.volume, DailyMarketQuote.volume),
                    "turnover": func.coalesce(stmt.excluded.turnover, DailyMarketQuote.turnover),
                    "transaction_count": func.coalesce(stmt.excluded.transaction_count, DailyMarketQuote.transaction_count),
                    "data_quality": stmt.excluded.data_quality,
                    "source": stmt.excluded.source,
                    "updated_at": func.now(),
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "trade_date"],
                    set_=update_dict,
                )
                res = await session.execute(stmt)
                return res.rowcount

    # ── 2. UPSERT 籌碼資料 ─────────────────────────────────────────────
    async def upsert_chips(self, records: List[Dict[str, Any]]) -> int:
        """整批 UPSERT 全市場三大法人與信用交易籌碼。"""
        if not records:
            return 0
        async with self._session_factory() as session:
            async with session.begin():
                stmt = pg_insert(DailyMarketChip).values(records)
                update_dict = {
                    "foreign_net": func.coalesce(stmt.excluded.foreign_net, DailyMarketChip.foreign_net),
                    "trust_net": func.coalesce(stmt.excluded.trust_net, DailyMarketChip.trust_net),
                    "dealer_net": func.coalesce(stmt.excluded.dealer_net, DailyMarketChip.dealer_net),
                    "institutional_net": func.coalesce(stmt.excluded.institutional_net, DailyMarketChip.institutional_net),
                    "margin_balance": func.coalesce(stmt.excluded.margin_balance, DailyMarketChip.margin_balance),
                    "margin_buy": func.coalesce(stmt.excluded.margin_buy, DailyMarketChip.margin_buy),
                    "margin_sell": func.coalesce(stmt.excluded.margin_sell, DailyMarketChip.margin_sell),
                    "margin_redeem": func.coalesce(stmt.excluded.margin_redeem, DailyMarketChip.margin_redeem),
                    "margin_quota": func.coalesce(stmt.excluded.margin_quota, DailyMarketChip.margin_quota),
                    "short_balance": func.coalesce(stmt.excluded.short_balance, DailyMarketChip.short_balance),
                    "short_buy": func.coalesce(stmt.excluded.short_buy, DailyMarketChip.short_buy),
                    "short_sell": func.coalesce(stmt.excluded.short_sell, DailyMarketChip.short_sell),
                    "short_redeem": func.coalesce(stmt.excluded.short_redeem, DailyMarketChip.short_redeem),
                    "offset_amount": func.coalesce(stmt.excluded.offset_amount, DailyMarketChip.offset_amount),
                    "data_quality": stmt.excluded.data_quality,
                    "source": stmt.excluded.source,
                    "updated_at": func.now(),
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "trade_date"],
                    set_=update_dict,
                )
                res = await session.execute(stmt)
                return res.rowcount

    # ── 3. UPSERT 估值與市值 ──────────────────────────────────────────
    async def upsert_valuation(self, records: List[Dict[str, Any]]) -> int:
        """整批 UPSERT 全市場 PE/PB/殖利率與市值。"""
        if not records:
            return 0
        async with self._session_factory() as session:
            async with session.begin():
                stmt = pg_insert(DailyValuation).values(records)
                update_dict = {
                    "pe_ratio": func.coalesce(stmt.excluded.pe_ratio, DailyValuation.pe_ratio),
                    "pb_ratio": func.coalesce(stmt.excluded.pb_ratio, DailyValuation.pb_ratio),
                    "dividend_yield": func.coalesce(stmt.excluded.dividend_yield, DailyValuation.dividend_yield),
                    "market_cap": func.coalesce(stmt.excluded.market_cap, DailyValuation.market_cap),
                    "mcap_rank": func.coalesce(stmt.excluded.mcap_rank, DailyValuation.mcap_rank),
                    "source": stmt.excluded.source,
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "trade_date"],
                    set_=update_dict,
                )
                res = await session.execute(stmt)
                return res.rowcount

    # ── 4. UPSERT 月營收 ──────────────────────────────────────────────
    async def upsert_revenue(self, records: List[Dict[str, Any]]) -> int:
        """整批 UPSERT 全市場每月營業收入。"""
        if not records:
            return 0
        async with self._session_factory() as session:
            async with session.begin():
                stmt = pg_insert(MonthlyRevenue).values(records)
                update_dict = {
                    "revenue": func.coalesce(stmt.excluded.revenue, MonthlyRevenue.revenue),
                    "mom_percent": func.coalesce(stmt.excluded.mom_percent, MonthlyRevenue.mom_percent),
                    "yoy_percent": func.coalesce(stmt.excluded.yoy_percent, MonthlyRevenue.yoy_percent),
                    "announced_date": func.coalesce(stmt.excluded.announced_date, MonthlyRevenue.announced_date),
                    "source": stmt.excluded.source,
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "year_month"],
                    set_=update_dict,
                )
                res = await session.execute(stmt)
                return res.rowcount

    # ── 5. 代碼主檔未知代號批次自動補入 ──────────────────────────────
    async def ensure_symbols_exist(self, symbols_meta: List[Dict[str, Any]], market_type: str = "tw") -> int:
        """寫入前確保主檔存在該代號（§3.6），避免 FK 違反導致整批寫入失敗。"""
        if not symbols_meta:
            return 0
        async with self._session_factory() as session:
            symbols = [m["symbol"] for m in symbols_meta]
            stmt = select(Symbol.symbol).where(Symbol.symbol.in_(symbols))
            res = await session.execute(stmt)
            existing = set(res.scalars().all())

            missing = [m for m in symbols_meta if m["symbol"] not in existing]
            if not missing:
                return 0

            records = [
                {
                    "symbol": m["symbol"],
                    "market_type": market_type,
                    "name": m.get("name") or m["symbol"],
                    "exchange": m.get("exchange") or "TWSE",
                    "security_type": m.get("security_type") or "股票",
                    "status": "active",
                    "is_active": True,
                }
                for m in missing
            ]
            stmt_insert = pg_insert(Symbol).values(records).on_conflict_do_nothing(index_elements=["symbol"])
            await session.execute(stmt_insert)
            await session.commit()
            logger.info(f"[代碼主檔] 自動補入 {len(records)} 筆未知代號: {[r['symbol'] for r in records[:5]]}...")
            return len(records)

    # ── 6. 計算缺漏日期（Data-Driven Resume，§3.9.2）─────────────────
    async def get_missing_dates(self, target: str, start_date: date, end_date: date, market_type: str = "tw") -> List[date]:
        """計算期望交易日 - 休市日 - 已有記錄的日期。"""
        async with self._session_factory() as session:
            # 1. 取得休市日
            no_trading_stmt = select(MarketNoTradingDay.trade_date).where(
                and_(
                    MarketNoTradingDay.market_type == market_type,
                    MarketNoTradingDay.trade_date >= start_date,
                    MarketNoTradingDay.trade_date <= end_date,
                )
            )
            res_nt = await session.execute(no_trading_stmt)
            no_trading_days = set(res_nt.scalars().all())

            # 2. 取得目標表中已有的日期（至少需要一定覆蓋率，如 500 筆以上才算完成）
            if target == "quote":
                model = DailyMarketQuote
            elif target == "chip":
                model = DailyMarketChip
            elif target == "valuation":
                model = DailyValuation
            else:
                model = DailyMarketQuote

            existing_stmt = (
                select(model.trade_date)
                .where(
                    and_(
                        model.market_type == market_type,
                        model.trade_date >= start_date,
                        model.trade_date <= end_date,
                        model.data_quality == "ok",
                    )
                )
                .group_by(model.trade_date)
                .having(func.count(model.symbol) >= 500)
            )
            res_ex = await session.execute(existing_stmt)
            existing_days = set(res_ex.scalars().all())

            # 3. 遍歷工作日
            missing = []
            curr = start_date
            while curr <= end_date:
                if curr.weekday() < 5:  # 週一至週五
                    if curr not in no_trading_days and curr not in existing_days:
                        missing.append(curr)
                curr += timedelta(days=1)
            return missing

    # ── 7. 全市場單日切片查詢（§8.4，支援分頁、篩選、排序白名單）──
    async def query_market_daily(
        self,
        trade_date: Optional[date] = None,
        market: str = "tw",
        exchange: Optional[str] = None,
        security_type: Optional[str] = None,
        industry: Optional[str] = None,
        q: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        num_filters: Optional[Dict[str, Tuple[Optional[float], Optional[float]]]] = None,
        sort: str = "turnover",
        order: str = "desc",
        page: int = 1,
        page_size: int = 50,
        include_delisted: bool = False,
        include_suspect: bool = False,
    ) -> Tuple[int, List[Dict[str, Any]], Optional[date]]:
        """全市場資料查詢 API 實作。"""
        if sort not in SORT_COLUMN_WHITELIST:
            raise ValueError(f"不合法的排序欄位：{sort}。允許的排序欄位包括：{list(SORT_COLUMN_WHITELIST.keys())}")

        async with self._session_factory() as session:
            # 若未指定日期，查詢最新一個有資料的日期
            if not trade_date:
                latest_date_stmt = (
                    select(DailyMarketQuote.trade_date)
                    .where(DailyMarketQuote.market_type == market)
                    .order_by(DailyMarketQuote.trade_date.desc())
                    .limit(1)
                )
                res = await session.execute(latest_date_stmt)
                trade_date = res.scalar_one_or_none()
                if not trade_date:
                    return 0, [], None

            # 建立 JOIN 查詢
            base_query = (
                select(
                    DailyMarketQuote.symbol,
                    Symbol.name,
                    DailyMarketQuote.exchange,
                    Symbol.security_type,
                    SymbolIndustry.industry_name,
                    DailyMarketQuote.open_price,
                    DailyMarketQuote.high_price,
                    DailyMarketQuote.low_price,
                    DailyMarketQuote.close_price,
                    DailyMarketQuote.change_amount,
                    DailyMarketQuote.change_percent,
                    DailyMarketQuote.volume,
                    DailyMarketQuote.turnover,
                    DailyMarketQuote.transaction_count,
                    DailyValuation.pe_ratio,
                    DailyValuation.pb_ratio,
                    DailyValuation.dividend_yield,
                    DailyValuation.market_cap,
                    DailyValuation.mcap_rank,
                    DailyMarketChip.foreign_net,
                    DailyMarketChip.trust_net,
                    DailyMarketChip.dealer_net,
                    DailyMarketChip.institutional_net,
                    DailyMarketChip.margin_balance,
                    DailyMarketChip.short_balance,
                    DailyMarketQuote.data_quality,
                )
                .join(Symbol, Symbol.symbol == DailyMarketQuote.symbol)
                .outerjoin(SymbolIndustry, SymbolIndustry.symbol == DailyMarketQuote.symbol)
                .outerjoin(
                    DailyValuation,
                    and_(
                        DailyValuation.symbol == DailyMarketQuote.symbol,
                        DailyValuation.trade_date == DailyMarketQuote.trade_date,
                    ),
                )
                .outerjoin(
                    DailyMarketChip,
                    and_(
                        DailyMarketChip.symbol == DailyMarketQuote.symbol,
                        DailyMarketChip.trade_date == DailyMarketQuote.trade_date,
                    ),
                )
                .where(
                    and_(
                        DailyMarketQuote.market_type == market,
                        DailyMarketQuote.trade_date == trade_date,
                    )
                )
            )

            # 過濾條件
            if not include_delisted:
                base_query = base_query.where(Symbol.status == "active")
            if not include_suspect:
                base_query = base_query.where(DailyMarketQuote.data_quality == "ok")
            if exchange:
                base_query = base_query.where(DailyMarketQuote.exchange == exchange)
            if security_type:
                base_query = base_query.where(Symbol.security_type == security_type)
            if industry:
                base_query = base_query.where(SymbolIndustry.industry_name == industry)
            if symbols:
                base_query = base_query.where(DailyMarketQuote.symbol.in_(symbols))
            if q:
                pattern = f"%{q.strip()}%"
                base_query = base_query.where(or_(DailyMarketQuote.symbol.ilike(pattern), Symbol.name.ilike(pattern)))

            # 數值區間篩選
            if num_filters:
                for col_name, (min_val, max_val) in num_filters.items():
                    col_obj = SORT_COLUMN_WHITELIST.get(col_name)
                    if col_obj is not None:
                        if min_val is not None:
                            base_query = base_query.where(col_obj >= min_val)
                        if max_val is not None:
                            base_query = base_query.where(col_obj <= max_val)

            # 1. 取得符合條件的總筆數
            count_stmt = select(func.count()).select_from(base_query.subquery())
            total_count = (await session.execute(count_stmt)).scalar_one()

            # 2. 排序與分頁 (NULLS LAST)
            sort_col = SORT_COLUMN_WHITELIST[sort]
            if order.lower() == "asc":
                order_expr = sort_col.asc().nullslast()
            else:
                order_expr = sort_col.desc().nullslast()

            offset = max(0, (page - 1) * page_size)
            page_query = base_query.order_by(order_expr).limit(page_size).offset(offset)
            res = await session.execute(page_query)
            rows = []
            for r in res.all():
                rows.append({
                    "symbol": r.symbol,
                    "name": r.name,
                    "exchange": r.exchange,
                    "security_type": r.security_type,
                    "industry": r.industry_name,
                    "open": float(r.open_price) if r.open_price is not None else None,
                    "high": float(r.high_price) if r.high_price is not None else None,
                    "low": float(r.low_price) if r.low_price is not None else None,
                    "close": float(r.close_price) if r.close_price is not None else None,
                    "change_amount": float(r.change_amount) if r.change_amount is not None else None,
                    "change_percent": float(r.change_percent) if r.change_percent is not None else None,
                    "volume": r.volume,
                    "turnover": r.turnover,
                    "transaction_count": r.transaction_count,
                    "pe_ratio": float(r.pe_ratio) if r.pe_ratio is not None else None,
                    "pb_ratio": float(r.pb_ratio) if r.pb_ratio is not None else None,
                    "dividend_yield": float(r.dividend_yield) if r.dividend_yield is not None else None,
                    "market_cap": r.market_cap,
                    "mcap_rank": r.mcap_rank,
                    "foreign_net": r.foreign_net,
                    "trust_net": r.trust_net,
                    "dealer_net": r.dealer_net,
                    "institutional_net": r.institutional_net,
                    "margin_balance": r.margin_balance,
                    "short_balance": r.short_balance,
                    "data_quality": r.data_quality,
                })

            return total_count, rows, trade_date

    # ── 8. 單一標的期間序列查詢（Fallback 與圖表使用）─────────────
    async def get_symbol_daily_series(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        market: str = "tw",
    ) -> List[Dict[str, Any]]:
        """取得單一股票在全市場表中的日序列（JOIN 行情與籌碼）。"""
        async with self._session_factory() as session:
            stmt = (
                select(
                    DailyMarketQuote.trade_date,
                    DailyMarketQuote.open_price,
                    DailyMarketQuote.high_price,
                    DailyMarketQuote.low_price,
                    DailyMarketQuote.close_price,
                    DailyMarketQuote.change_amount,
                    DailyMarketQuote.change_percent,
                    DailyMarketQuote.volume,
                    DailyMarketQuote.turnover,
                    DailyMarketChip.foreign_net,
                    DailyMarketChip.trust_net,
                    DailyMarketChip.dealer_net,
                    DailyMarketChip.institutional_net,
                    DailyMarketChip.margin_balance,
                    DailyMarketChip.short_balance,
                )
                .outerjoin(
                    DailyMarketChip,
                    and_(
                        DailyMarketChip.symbol == DailyMarketQuote.symbol,
                        DailyMarketChip.trade_date == DailyMarketQuote.trade_date,
                    ),
                )
                .where(
                    and_(
                        DailyMarketQuote.symbol == symbol,
                        DailyMarketQuote.market_type == market,
                    )
                )
            )
            if start_date:
                stmt = stmt.where(DailyMarketQuote.trade_date >= start_date)
            if end_date:
                stmt = stmt.where(DailyMarketQuote.trade_date <= end_date)
            stmt = stmt.order_by(DailyMarketQuote.trade_date.asc())

            res = await session.execute(stmt)
            records = []
            for r in res.all():
                d_str = r.trade_date.strftime("%Y-%m-%d") if isinstance(r.trade_date, date) else str(r.trade_date)
                records.append({
                    "date": d_str,
                    "trade_date": d_str,
                    "open": float(r.open_price) if r.open_price is not None else None,
                    "high": float(r.high_price) if r.high_price is not None else None,
                    "low": float(r.low_price) if r.low_price is not None else None,
                    "close": float(r.close_price) if r.close_price is not None else None,
                    "change": float(r.change_amount) if r.change_amount is not None else None,
                    "change_pct": float(r.change_percent) if r.change_percent is not None else None,
                    "volume": r.volume,
                    "amount": r.turnover,
                    # 股 → 張採無條件捨去絕對值（int(x/1000)），不可用 `// 1000`：floor division
                    # 對負數（賣超）會系統性多算 1 張，例如 -1500 // 1000 = -2 而非正確的 -1
                    # （見 services/fetcher.py 的 _lots() 同一份修正）。
                    "foreign_buy_sell": int(r.foreign_net / 1000) if r.foreign_net is not None else None,
                    "trust_buy_sell": int(r.trust_net / 1000) if r.trust_net is not None else None,
                    "dealer_buy_sell": int(r.dealer_net / 1000) if r.dealer_net is not None else None,
                    "institutional_total": int(r.institutional_net / 1000) if r.institutional_net is not None else None,
                    "margin_balance": r.margin_balance,
                    "short_balance": r.short_balance,
                })
            return records

    # ── 9. 批次預載（MarketPreload，§4.3）─────────────────────────────
    async def preload_market_data(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        market: str = "tw",
        batch_size: int = 500,
    ) -> Dict[str, Any]:
        """批次載入選股池所需全部數據，避免 N+1 查詢。"""
        quotes_by_sym: Dict[str, List[dict]] = {}
        valuation_by_sym: Dict[str, Dict[str, dict]] = {}  # {symbol: {date_str: {pe, pb, yield}}}
        revenue_by_sym: Dict[str, Dict[str, dict]] = {}    # {symbol: {year_month: {revenue, mom, yoy}}}

        async with self._session_factory() as session:
            # 1. 批次查詢行情與籌碼
            for i in range(0, len(symbols), batch_size):
                chunk = symbols[i : i + batch_size]
                q_stmt = (
                    select(
                        DailyMarketQuote.symbol,
                        DailyMarketQuote.trade_date,
                        DailyMarketQuote.open_price,
                        DailyMarketQuote.high_price,
                        DailyMarketQuote.low_price,
                        DailyMarketQuote.close_price,
                        DailyMarketQuote.change_amount,
                        DailyMarketQuote.change_percent,
                        DailyMarketQuote.volume,
                        DailyMarketQuote.turnover,
                        DailyMarketChip.foreign_net,
                        DailyMarketChip.trust_net,
                        DailyMarketChip.dealer_net,
                        DailyMarketChip.institutional_net,
                        DailyMarketChip.margin_balance,
                        DailyMarketChip.short_balance,
                    )
                    .outerjoin(
                        DailyMarketChip,
                        and_(
                            DailyMarketChip.symbol == DailyMarketQuote.symbol,
                            DailyMarketChip.trade_date == DailyMarketQuote.trade_date,
                        ),
                    )
                    .where(
                        and_(
                            DailyMarketQuote.symbol.in_(chunk),
                            DailyMarketQuote.market_type == market,
                            DailyMarketQuote.trade_date >= start_date,
                            DailyMarketQuote.trade_date <= end_date,
                            DailyMarketQuote.data_quality == "ok",
                        )
                    )
                    .order_by(DailyMarketQuote.symbol, DailyMarketQuote.trade_date.asc())
                )
                res = await session.execute(q_stmt)
                for r in res.all():
                    d_str = r.trade_date.strftime("%Y-%m-%d")
                    item = {
                        "date": d_str,
                        "trade_date": d_str,
                        "open": float(r.open_price) if r.open_price is not None else None,
                        "high": float(r.high_price) if r.high_price is not None else None,
                        "low": float(r.low_price) if r.low_price is not None else None,
                        "close": float(r.close_price) if r.close_price is not None else None,
                        "change": float(r.change_amount) if r.change_amount is not None else None,
                        "change_pct": float(r.change_percent) if r.change_percent is not None else None,
                        "volume": r.volume,
                        "amount": r.turnover,
                        # 同上：股 → 張須用截斷向零，不可用 `// 1000`（floor division 對負數多算 1 張）
                        "foreign_buy_sell": int(r.foreign_net / 1000) if r.foreign_net is not None else None,
                        "trust_buy_sell": int(r.trust_net / 1000) if r.trust_net is not None else None,
                        "dealer_buy_sell": int(r.dealer_net / 1000) if r.dealer_net is not None else None,
                        "institutional_total": int(r.institutional_net / 1000) if r.institutional_net is not None else None,
                        "margin_balance": r.margin_balance,
                        "short_balance": r.short_balance,
                    }
                    quotes_by_sym.setdefault(r.symbol, []).append(item)

            # 2. 批次查詢估值
            for i in range(0, len(symbols), batch_size):
                chunk = symbols[i : i + batch_size]
                v_stmt = (
                    select(
                        DailyValuation.symbol,
                        DailyValuation.trade_date,
                        DailyValuation.pe_ratio,
                        DailyValuation.pb_ratio,
                        DailyValuation.dividend_yield,
                        DailyValuation.market_cap,
                        DailyValuation.mcap_rank,
                    )
                    .where(
                        and_(
                            DailyValuation.symbol.in_(chunk),
                            DailyValuation.market_type == market,
                            DailyValuation.trade_date >= start_date,
                            DailyValuation.trade_date <= end_date,
                        )
                    )
                )
                res = await session.execute(v_stmt)
                for r in res.all():
                    d_str = r.trade_date.strftime("%Y-%m-%d")
                    val_map = valuation_by_sym.setdefault(r.symbol, {})
                    val_map[d_str] = {
                        "pe_ratio": float(r.pe_ratio) if r.pe_ratio is not None else None,
                        "pb_ratio": float(r.pb_ratio) if r.pb_ratio is not None else None,
                        "dividend_yield": float(r.dividend_yield) if r.dividend_yield is not None else None,
                        "market_cap": r.market_cap,
                        "mcap_rank": r.mcap_rank,
                    }

            # 3. 批次查詢月營收
            for i in range(0, len(symbols), batch_size):
                chunk = symbols[i : i + batch_size]
                r_stmt = (
                    select(
                        MonthlyRevenue.symbol,
                        MonthlyRevenue.year_month,
                        MonthlyRevenue.revenue,
                        MonthlyRevenue.mom_percent,
                        MonthlyRevenue.yoy_percent,
                        MonthlyRevenue.announced_date,
                    )
                    .where(
                        and_(
                            MonthlyRevenue.symbol.in_(chunk),
                            MonthlyRevenue.market_type == market,
                        )
                    )
                )
                res = await session.execute(r_stmt)
                for r in res.all():
                    rev_map = revenue_by_sym.setdefault(r.symbol, {})
                    rev_map[r.year_month] = {
                        "revenue": r.revenue,
                        "mom_percent": float(r.mom_percent) if r.mom_percent is not None else None,
                        "yoy_percent": float(r.yoy_percent) if r.yoy_percent is not None else None,
                        "announced_date": r.announced_date.strftime("%Y-%m-%d") if r.announced_date else None,
                    }

        return {
            "quotes": quotes_by_sym,
            "valuation": valuation_by_sym,
            "revenue": revenue_by_sym,
        }

    # ── 10. 取得有資料的交易日清單 ──────────────────────────────────
    async def get_available_dates(self, market: str = "tw", limit: int = 60) -> List[str]:
        """回傳最新有資料的日期清單。"""
        async with self._session_factory() as session:
            stmt = (
                select(DailyMarketQuote.trade_date)
                .where(DailyMarketQuote.market_type == market)
                .distinct(DailyMarketQuote.trade_date)
                .order_by(DailyMarketQuote.trade_date.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            return [d.strftime("%Y-%m-%d") for d in res.scalars().all()]

    # ── 11. 取得全市場資料庫狀態與健康指標 ──────────────────────────
    async def get_market_status(self, market: str = "tw") -> Dict[str, Any]:
        """回傳全市場各表最新狀態、筆數統計與最近 Job。"""
        async with self._session_factory() as session:
            latest_date_stmt = (
                select(DailyMarketQuote.trade_date)
                .where(DailyMarketQuote.market_type == market)
                .order_by(DailyMarketQuote.trade_date.desc())
                .limit(1)
            )
            latest_date = (await session.execute(latest_date_stmt)).scalar_one_or_none()

            stats = {"latest_trade_date": latest_date.strftime("%Y-%m-%d") if latest_date else None}
            if latest_date:
                # 統計最新一日各表筆數
                q_count = (await session.execute(
                    select(func.count()).where(and_(DailyMarketQuote.trade_date == latest_date, DailyMarketQuote.market_type == market))
                )).scalar_one()
                q_suspect = (await session.execute(
                    select(func.count()).where(and_(DailyMarketQuote.trade_date == latest_date, DailyMarketQuote.data_quality == "suspect"))
                )).scalar_one()
                c_count = (await session.execute(
                    select(func.count()).where(and_(DailyMarketChip.trade_date == latest_date, DailyMarketChip.market_type == market))
                )).scalar_one()
                v_count = (await session.execute(
                    select(func.count()).where(and_(DailyValuation.trade_date == latest_date, DailyValuation.market_type == market))
                )).scalar_one()
                stats["quote_count"] = q_count
                stats["quote_suspect"] = q_suspect
                stats["chip_count"] = c_count
                stats["valuation_count"] = v_count

            # 最近一筆 Job
            job_stmt = select(MarketFetchJob).order_by(MarketFetchJob.id.desc()).limit(1)
            job = (await session.execute(job_stmt)).scalar_one_or_none()
            if job:
                stats["last_job"] = {
                    "id": job.id,
                    "scope": job.scope,
                    "status": job.status,
                    "start_date": str(job.start_date),
                    "end_date": str(job.end_date),
                    "cursor_date": str(job.cursor_date) if job.cursor_date else None,
                    "total_days": job.total_days,
                    "done_days": job.done_days,
                    "failed_days": job.failed_days,
                    "last_error": job.last_error,
                    "created_at": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else None,
                }
            else:
                stats["last_job"] = None

            return stats

    # ── 12. 作業管理 (MarketFetchJob) ─────────────────────────────────
    async def create_fetch_job(
        self, scope: str, targets: str, start_date: date, end_date: date, total_days: int, trigger_type: str = "schedule"
    ) -> int:
        """新建作業紀錄。若已有 status='running' 的作業，V10 的部分唯一索引會讓本次 INSERT
        違反唯一性約束，轉為 ActiveFetchJobError 讓呼叫端得知並優雅結束，不當機、不重複執行。"""
        async with self._session_factory() as session:
            job = MarketFetchJob(
                scope=scope,
                targets=targets,
                start_date=start_date,
                end_date=end_date,
                total_days=total_days,
                trigger_type=trigger_type,
                status="running",
            )
            session.add(job)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise ActiveFetchJobError("已有全市場抓取／回補作業正在執行中") from e
            await session.refresh(job)
            return job.id

    async def update_job_progress(
        self, job_id: int, cursor_date: date, done_days: int, failed_days: int, last_error: Optional[str] = None
    ) -> None:
        async with self._session_factory() as session:
            stmt = (
                pg_insert(MarketFetchJob)
                .values(
                    id=job_id,
                    cursor_date=cursor_date,
                    done_days=done_days,
                    failed_days=failed_days,
                    last_error=last_error,
                    updated_at=func.now(),
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "cursor_date": cursor_date,
                        "done_days": done_days,
                        "failed_days": failed_days,
                        "last_error": last_error,
                        "updated_at": func.now(),
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def complete_fetch_job(self, job_id: int, status: str = "completed") -> None:
        async with self._session_factory() as session:
            job = await session.get(MarketFetchJob, job_id)
            if job:
                job.status = status
                job.updated_at = datetime.now()
                await session.commit()

    async def get_active_fetch_job(self) -> Optional[dict]:
        async with self._session_factory() as session:
            stmt = select(MarketFetchJob).where(MarketFetchJob.status == "running").order_by(MarketFetchJob.id.desc()).limit(1)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return None
            return {
                "id": job.id,
                "scope": job.scope,
                "status": job.status,
                "start_date": str(job.start_date),
                "end_date": str(job.end_date),
                "cursor_date": str(job.cursor_date) if job.cursor_date else None,
                "total_days": job.total_days,
                "done_days": job.done_days,
                "failed_days": job.failed_days,
            }
