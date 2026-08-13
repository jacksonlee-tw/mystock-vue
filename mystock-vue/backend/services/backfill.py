"""系統啟動時的歷史缺漏檢查與自動回補（見主文件第 5.2 節、phase3_5 設計文件第 3.5 節）。

以 market_no_trading_days ∪ daily_stock_data 判斷缺漏，區分「沒抓到」與「當天沒開盤」，
避免每次啟動都對假日重複發動抓取。以背景任務執行（見 main.py 的 lifespan），不阻塞服務啟動。
"""
import asyncio
import logging
from datetime import date, timedelta
from typing import List, Tuple

from config import get_backfill_max_days, get_data_source, get_enabled_markets, get_target_stocks
from repositories.stock_repository import StockRepository
from services.fetcher import run_fetch_process
from services.us_fetcher import run_us_fetch_process

logger = logging.getLogger("mystock-backend")


async def _compute_missing_symbols(repo: StockRepository, market: str, max_days: int) -> Tuple[List[str], int]:
    no_trading_days = await repo.get_no_trading_days(market)
    today = date.today()
    expected_weekdays = {
        today - timedelta(days=i)
        for i in range(max_days)
        if (today - timedelta(days=i)).weekday() < 5
    } - no_trading_days

    missing_symbols = []
    max_gap_days = 0
    for symbol in get_target_stocks(market=market):
        rows = await repo.get_daily_data(symbol)
        existing_dates = {row["trade_date"] for row in rows}
        missing = expected_weekdays - existing_dates
        if missing:
            missing_symbols.append(symbol)
            max_gap_days = max(max_gap_days, (today - min(missing)).days + 1)

    return missing_symbols, max_gap_days


async def run_startup_backfill() -> None:
    # 缺漏偵測靠查詢 daily_stock_data / market_no_trading_days 兩張表，只有 DATA_SOURCE=postgres
    # 時才有意義；json 模式下沒有 Postgres 可查，跑下去只會每次啟動都連線失敗噴警告，直接跳過。
    if get_data_source() != "postgres":
        logger.info("[啟動回補] DATA_SOURCE 非 postgres，略過啟動回補檢查")
        return

    repo = StockRepository()
    max_days = get_backfill_max_days()

    for market in get_enabled_markets():
        try:
            missing_symbols, gap_days = await _compute_missing_symbols(repo, market, max_days)
            if not missing_symbols:
                continue

            months = max(1, gap_days // 30 + 1)
            logger.info(f"[啟動回補] {market} 偵測到 {len(missing_symbols)} 檔缺漏，回補近 {months} 個月: {missing_symbols}")

            fetch_fn = run_us_fetch_process if market == "us" else run_fetch_process
            await asyncio.to_thread(
                fetch_fn, target_stocks=missing_symbols, months=months,
                mode="repair", trigger_type="backfill",
            )
        except Exception as e:
            logger.warning(f"[啟動回補] {market} 執行失敗: {e}")
