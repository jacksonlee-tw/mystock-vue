"""
services/macro_analytics.py
大盤環境位階查詢（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §5.2）。

**不重建指數管線**（§1.3「大盤位階不重算」）：收盤價序列直接重用既有
`services/stock_service.load_stock_data()`／`aggregate_stock_data()`（`services/index_service.py`
內部也是同一組函式），本模組只多算「20MA／60MA 位階」這一層既有指數服務沒有的判斷。均線計算
沿用 `indicators/moving_average.py` 的 `sma()`，不重寫演算法（與策略引擎 `ScanContext.ma`
用同一套實作，數字才會一致）。

`macro_flags`（§5.2 全域鎖）實際掛進 `ScanContext` 並在 `strategies/scanner.py` 迴圈外算一次
屬於 P4 範疇（見規格書 §15.2 P4 列）；`get_market_regime()` 是底層查詢函式，`get_macro_flags()`
是 P4 `strategies/scanner.py` 實際呼叫的組裝層——兩者分開是因為 `market-regime` API 端點
（P3 既有）要看到完整數字（收盤價、均線值、漲跌幅），`macro_flags` 只需要布林旗標給
`macro_filter` condition 讀。
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


async def get_macro_flags(market: str = "tw") -> Dict[str, bool]:
    """P4 §6.2 `ScanContext.macro_flags`：`strategies/scanner.py` 在
    `for symbol in all_scan_symbols:` 迴圈**之前**呼叫一次（AC-P4-06「全市場一次」），
    回傳的 dict 原封不動注入該次掃描的每一個 `ScanContext`，不逐檔個股重算。

    旗標鍵名帶 `market` 前綴（`tw_above_20ma`／`us_above_20ma` 等）：`macro_filter`
    condition（`strategies/conditions_macro.py`）用 `ctx.market` 组出對應鍵名讀取，
    同一個 dict 可以不分市場直接沿用（雖然目前 `scan_market()` 每次只服務單一市場，
    這裡仍以完整鍵名設計，避免未來要合併查詢時再改一次介面）。

    **目前只涵蓋 20MA／60MA 位階**：§5.2 提到的「總經指標同向轉緊（例如 10 年期殖利率
    短期急升）」原文只是舉例、未給出具體的判定門檻（漲幅多少算「急升」、回看幾天），
    規格書 §15.4 也沒有把這個落差點補上——不無中生有一個門檻數字，等之後有具體門檻
    再補這個 flag，避免用猜的業務規則误导使用者。無資料時回傳空 dict（不是缺 key
    的部分填 False，是整個 dict 為空），讓 scanner.py 的 `requires=("macro_flags",)`
    自然把 `macro_filter` 條件整個跳過（比照 `revenue_yoy` 等既有欄位「空即跳過」的慣例）。
    """
    regime = await get_market_regime(market)
    if not regime.get("has_data"):
        return {}
    flags: Dict[str, bool] = {}
    if regime.get("above_ma20") is not None:
        flags[f"{market}_above_20ma"] = regime["above_ma20"]
    if regime.get("above_ma60") is not None:
        flags[f"{market}_above_60ma"] = regime["above_ma60"]
    return flags
