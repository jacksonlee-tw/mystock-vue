"""
services/macro_analytics.py
大盤環境位階查詢（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §5.2）。

**不重建指數管線**（§1.3「大盤位階不重算」）：收盤價序列直接重用既有
`services/stock_service.load_stock_data()`／`aggregate_stock_data()`（`services/index_service.py`
內部也是同一組函式），本模組只多算「20MA／60MA 位階」這一層既有指數服務沒有的判斷。均線計算
沿用 `indicators/moving_average.py` 的 `sma()`，不重寫演算法（與策略引擎 `ScanContext.ma`
用同一套實作，數字才會一致）。

`macro_flags`（§5.2 全域鎖）實際掛進 `ScanContext` 並在 `strategies/scanner.py` 迴圈外算一次
屬於 P4 範疇（見規格書 §15.2 P4 列）；本模組提供的 `get_market_regime()` 是 P4 會呼叫的底層
查詢函式，也供 P3 驗證與未來 API／前端使用。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from indicators.moving_average import sma
from services.stock_service import aggregate_stock_data, load_stock_data

# §1.3／§5.2：全域鎖涵蓋 TW（加權指數）與 US（S&P 500），對齊 index_config/indices.yaml 既有代號。
DEFAULT_INDEX_CODE: Dict[str, str] = {"tw": "TWII", "us": "GSPC"}


async def get_market_regime(market: str = "tw") -> Dict[str, Any]:
    """回傳指定市場大盤指數的最新收盤、20MA／60MA 與是否站上均線。

    資料不足 60 個交易日時 `ma60`／`above_ma60` 為 `None`（比照 `indicators/moving_average.sma()`
    「窗口不足即留空、不補值」的既有慣例），不得以 0 或錯誤外插值代入。
    """
    index_code = DEFAULT_INDEX_CODE.get(market)
    if not index_code:
        return {"market": market, "has_data": False, "reason": "unsupported_market"}

    raw = await load_stock_data(index_code, market, kind="index")
    aggregated = aggregate_stock_data(raw, period="daily", months=6) if raw else []
    if len(aggregated) < 2:
        return {"market": market, "index_code": index_code, "has_data": False, "reason": "insufficient_history"}

    # 收盤 0 視為缺值（既有慣例：0 是抓取失敗的落地佔位值，不是合法報價，見 services/fetcher.py 註記）
    closes = [r.get("close") or None for r in aggregated]
    ma20_series = sma(closes, 20)
    ma60_series = sma(closes, 60)

    latest_close: Optional[float] = closes[-1]
    prev_close: Optional[float] = closes[-2]
    ma20 = ma20_series[-1]
    ma60 = ma60_series[-1]
    change_pct = (
        round((latest_close - prev_close) / prev_close * 100, 2)
        if latest_close is not None and prev_close else None
    )

    return {
        "market": market, "index_code": index_code, "has_data": True,
        "latest_date": aggregated[-1].get("date"),
        "close": latest_close,
        "ma20": ma20, "ma60": ma60,
        "above_ma20": (latest_close >= ma20) if latest_close is not None and ma20 is not None else None,
        "above_ma60": (latest_close >= ma60) if latest_close is not None and ma60 is not None else None,
        "daily_change_pct": change_pct,
    }
