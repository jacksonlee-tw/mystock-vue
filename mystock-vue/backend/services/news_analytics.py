"""
services/news_analytics.py
個股情緒動能與 Buzz Surge 查詢（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §4.3）。

純粹是「組裝」層：從 NewsRepository／news_sources.yaml／StockRepository 取資料，交給
indicators/news_time.py 的純函式計算，兩邊都不重算對方的邏輯（比照 strategies/scanner.py
「condition 只讀 ctx.ma，不重算指標」的既有分工精神，這裡是同一精神套用到新聞情緒）。

`sentiment_5d`／Buzz Surge 前後端共用同一份結果（§4.3 明文「不各算一套」）：本模組即是那個
唯一計算入口，供 API 端點（P2 驗證用）與未來 P4 的 ScanContext 擴充共同呼叫。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from db.session import get_async_session
from indicators.news_time import (
    buzz_surge_ratio, is_weekday_trading_day, recent_trading_dates, weighted_sentiment_avg,
)
from repositories.news_repository import NewsRepository
from repositories.stock_repository import StockRepository
from services.news_config import load_news_sources_config

BUZZ_SURGE_WINDOW_DAYS = 20  # §4.3：近 20 交易日平均則數


async def _trading_day_checker(market_type: str):
    no_trading_days = await StockRepository().get_no_trading_days(market_type)
    return is_weekday_trading_day(no_trading_days)


async def get_sentiment_5d(symbol: str, market_type: str = "tw", as_of: Optional[date] = None) -> Optional[float]:
    """§4.3 5 日加權情緒分數：對近 `sentiment_window_days`（news_sources.yaml 預設 5）個
    交易日、`is_duplicate = false` 的新聞取來源權重加權平均。`as_of` 預設今天，供未來排程
    重算歷史某一天使用（不含 `as_of` 之後的資料，避免 look-ahead）。"""
    as_of = as_of or date.today()
    config = load_news_sources_config()
    is_trading_day = await _trading_day_checker(market_type)
    window_dates = recent_trading_dates(as_of, config.sentiment_window_days, is_trading_day)
    since_date = window_dates[0]

    async with get_async_session() as session:
        rows = await NewsRepository(session).get_recent_scores(
            symbol=symbol, market_type=market_type, since_date=since_date,
        )
    weights = {s.id: s.weight for s in config.sources}
    return weighted_sentiment_avg(rows, weights)


async def get_buzz_surge(symbol: str, market_type: str = "tw", as_of: Optional[date] = None) -> Optional[float]:
    """§4.3 Buzz Surge（新聞曝光倍數）：當日新聞則數 / 近 20 交易日平均則數
    （不含當日，見 `indicators/news_time.buzz_surge_ratio()` docstring）。"""
    as_of = as_of or date.today()
    is_trading_day = await _trading_day_checker(market_type)
    # 含當日在內取 window+1 個交易日，扣掉最後一筆（當日）才是「近 20 交易日」歷史
    all_dates = recent_trading_dates(as_of, BUZZ_SURGE_WINDOW_DAYS + 1, is_trading_day)
    history_dates, today_bucket = all_dates[:-1], all_dates[-1]

    async with get_async_session() as session:
        counts = await NewsRepository(session).get_news_count_by_dates(
            symbol=symbol, market_type=market_type, dates=all_dates,
        )
    today_count = counts.get(today_bucket, 0)
    history_counts = [counts[d] for d in history_dates]
    return buzz_surge_ratio(today_count, history_counts)


async def get_sentiment_summary(symbol: str, market_type: str = "tw") -> dict:
    """API 端點使用的組合摘要（見 api/v1/endpoints/news.py 的 `/sentiment-summary`）。"""
    sentiment_5d = await get_sentiment_5d(symbol, market_type)
    buzz_surge = await get_buzz_surge(symbol, market_type)
    return {
        "symbol": symbol, "market_type": market_type,
        "sentiment_5d": sentiment_5d, "buzz_surge": buzz_surge,
        "as_of": date.today().isoformat(),
    }
