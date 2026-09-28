"""市場「預期最新交易日」判斷（見 docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.2）。

給 `services/freshness_service.py` 用來判斷「這個市場現在應該已經有收盤資料到哪一天」，
逐檔比對追蹤清單／指數的最後資料日期是否落後。純函式、可注入 `now`，方便單元測試。

- `tw`：直接委派既有的 `services.index_fetcher.get_latest_expected_tw_trading_date()`
  （14:30 Asia/Taipei cutoff、週末、`_no_trading_days.json`），**不搬動原函式**，避免影響
  `/api/v1/indices/sync` 既有行為（規劃書 §3.2 表格）。
- `us`：以 `America/New_York` 時間判斷；平日且已過 17:00 ET（收盤 16:00 後留 1 小時讓
  yfinance 日線資料就緒）視為當天已可用，否則退回前一天，再往前跳過週末與
  `US_MARKET_HOLIDAYS`。

兩者皆非完整的交易所行事曆（規劃書 T2 已知取捨）：判斷錯誤的後果最多是多打一次
TWSE／yfinance（仍會被呼叫端的節流鍵擋住不會重複補抓），不會漏抓。
"""
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from typing import Optional

import pytz

from services.index_fetcher import get_latest_expected_tw_trading_date

_US_TZ = pytz.timezone("America/New_York")
# 收盤 16:00 ET 後留 1 小時緩衝，讓 yfinance 的日線資料來得及就緒（規劃書 §3.2）
_US_DATA_READY_CUTOFF = dt_time(17, 0)

# NYSE 全日休市日（2025–2027，來源：NYSE 官方休市行事曆 www.nyse.com/markets/hours-calendars）。
# ADR-04：以模組內常數取代 `holidays` / `pandas_market_calendars` 相依套件，換來的省下的成本
# 有限（見規劃書取捨），節流鍵已兜底誤差。**每年 12 月請補上下一年的日期**，否則新年度會退化成
# 「只靠週末判斷」，多補抓幾次（不影響正確性，只是效率）。
US_MARKET_HOLIDAYS = {
    # 2025
    "2025-01-01",  # New Year's Day
    "2025-01-20",  # Martin Luther King Jr. Day
    "2025-02-17",  # Washington's Birthday
    "2025-04-18",  # Good Friday
    "2025-05-26",  # Memorial Day
    "2025-06-19",  # Juneteenth
    "2025-07-04",  # Independence Day
    "2025-09-01",  # Labor Day
    "2025-11-27",  # Thanksgiving Day
    "2025-12-25",  # Christmas Day
    # 2026
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # Martin Luther King Jr. Day
    "2026-02-16",  # Washington's Birthday
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day（觀察日，7/4 為週六）
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving Day
    "2026-12-25",  # Christmas Day
    # 2027
    "2027-01-01",  # New Year's Day
    "2027-01-18",  # Martin Luther King Jr. Day
    "2027-02-15",  # Washington's Birthday
    "2027-03-26",  # Good Friday
    "2027-05-31",  # Memorial Day
    "2027-06-18",  # Juneteenth（觀察日，6/19 為週六）
    "2027-07-05",  # Independence Day（觀察日，7/4 為週日）
    "2027-09-06",  # Labor Day
    "2027-11-25",  # Thanksgiving Day
    "2027-12-24",  # Christmas Day（觀察日，12/25 為週六）
}


def _get_latest_expected_us_trading_date(now: Optional[datetime] = None) -> str:
    """美股版本，規則見模組頂部說明與規劃書 §3.2。"""
    current = now or datetime.now(_US_TZ)
    current = _US_TZ.localize(current) if current.tzinfo is None else current.astimezone(_US_TZ)

    candidate = current.date()
    if current.weekday() >= 5 or current.time() < _US_DATA_READY_CUTOFF:
        candidate -= timedelta(days=1)

    while candidate.weekday() >= 5 or candidate.strftime("%Y-%m-%d") in US_MARKET_HOLIDAYS:
        candidate -= timedelta(days=1)

    return candidate.strftime("%Y-%m-%d")


def get_latest_expected_trading_date(market: str, now: Optional[datetime] = None) -> str:
    """回傳指定市場「預期」應已有資料的最新交易日（YYYY-MM-DD），與 JSON 資料日期鍵同格式，
    可直接字串比較。`now` 可注入以利測試；未帶入時取各市場當地現在時間。"""
    if market == "tw":
        return get_latest_expected_tw_trading_date(now)
    if market == "us":
        return _get_latest_expected_us_trading_date(now)
    raise ValueError(f"不支援的市場：{market}")
