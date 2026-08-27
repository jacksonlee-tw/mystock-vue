"""
ai/summary.py
量化摘要組裝（見規格書 §4.2）。唯一呼叫 services/stock_service.get_stock_chart_payload() 之處——
本模組不得自行計算任何指標（沿用策略引擎的同一條約束：只能讀既算好的序列，不得重算）。

輸出即快照：build_quant_summary() 回傳的 .summary 會原樣存入 ai_analysis_report.quant_summary
（ADR-AI-15），也是送給 LLM 的量化數值來源。
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from services.stock_service import get_stock_chart_payload
from indicators.chip import cum_net

MA_KEYS = ["MA5", "MA10", "MA20", "MA60", "MA120", "MA240"]


@dataclass
class QuantSummary:
    symbol: str
    market: str
    stock_name: str
    trade_date: date
    chart_period: str
    chart_months: int
    chart_start_date: Optional[date]
    chart_end_date: Optional[date]
    summary: dict[str, Any]


def _parse_date(value: Optional[str]) -> Optional[date]:
    """get_stock_chart_payload() 的 start_date/end_date 是 'YYYY-MM-DD' 字串；
    asyncpg 對 DATE 欄位不接受字串參數，必須先轉成 date 物件才能寫入
    ai_analysis_report.chart_start_date/chart_end_date（DATE 型別）。"""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _clean(v):
    """0／None 一律視為缺值（本專案慣例：0 代表未回補到行情，見 stock_service 註解），
    不送給 AI，避免模型把 0 當成真實價位（§4.2 空值處理）。"""
    if v is None or v == 0:
        return None
    return v


def _round(v, digits: int = 2):
    if v is None:
        return None
    try:
        return round(float(v), digits)
    except (TypeError, ValueError):
        return None


async def build_quant_summary(symbol: str, market: str, period: str, months: int) -> Optional[QuantSummary]:
    payload = await get_stock_chart_payload(symbol, period=period, months=months, market=market)
    if payload.get("error"):
        return None

    records = payload.get("records") or []
    dates = payload.get("dates") or []
    if not records:
        return None

    latest = payload.get("latest_summary") or {}
    ma = payload.get("moving_averages") or {}
    kd = payload.get("kd") or {}
    idx = len(records) - 1

    trade_date_str = latest.get("date") or (dates[-1] if dates else None)
    if not trade_date_str:
        return None
    trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()

    close = _clean(latest.get("close"))

    summary: dict[str, Any] = {"symbol": symbol, "market": market, "date": trade_date_str}

    latest_block = {
        "close": _round(close),
        "open": _round(_clean(latest.get("open"))),
        "high": _round(_clean(latest.get("high"))),
        "low": _round(_clean(latest.get("low"))),
        "volume": _clean(records[idx].get("volume")),
    }
    prev_close = _clean(records[idx - 1].get("close")) if idx >= 1 else None
    if close is not None and prev_close:
        latest_block["change_pct"] = _round((close - prev_close) / prev_close * 100)
    latest_block = {k: v for k, v in latest_block.items() if v is not None}
    if latest_block:
        summary["latest"] = latest_block

    ma_block: dict[str, float] = {}
    bias_block: dict[str, float] = {}
    for key in MA_KEYS:
        series = ma.get(key) or []
        val = _clean(series[idx]) if idx < len(series) else None
        if val is None:
            continue
        short_key = key.lower()
        ma_block[short_key] = _round(val)
        if close is not None and val:
            bias_block[short_key] = _round((close - val) / val * 100)
    if ma_block:
        summary["ma"] = ma_block
    if bias_block:
        summary["bias_percent"] = bias_block

    k_series = kd.get("k") or []
    d_series = kd.get("d") or []
    if idx < len(k_series) and k_series[idx] is not None:
        summary["kd"] = {
            "k": _round(k_series[idx]),
            "d": _round(d_series[idx]) if idx < len(d_series) else None,
        }

    highs = [r.get("high") for r in records if r.get("high")]
    lows = [r.get("low") for r in records if r.get("low")]
    if highs and lows:
        range_high, range_low = max(highs), min(lows)
        high_date = next((r["date"] for r in records if r.get("high") == range_high), None)
        low_date = next((r["date"] for r in records if r.get("low") == range_low), None)
        summary["range"] = {
            "high": _round(range_high), "high_date": high_date,
            "low": _round(range_low), "low_date": low_date,
        }

    volumes = [r.get("volume") for r in records if r.get("volume")]
    if len(volumes) >= 5:
        vol_ma5 = sum(volumes[-5:]) / 5
        summary["volume_ma5"] = round(vol_ma5)
        if latest_block.get("volume") and vol_ma5:
            summary["volume_ratio"] = _round(latest_block["volume"] / vol_ma5)

    # 三大法人／融資融券：僅 TW（§4.2）
    if market == "tw":
        chip_block: dict[str, float] = {}
        for field, key in (
            ("foreign_buy_sell", "foreign_net_5d"),
            ("trust_buy_sell", "trust_net_5d"),
            ("dealer_buy_sell", "dealer_net_5d"),
        ):
            net = cum_net(records, field, idx, 5)
            if net:
                chip_block[key] = round(net)
        if chip_block:
            summary["chips"] = chip_block

        margin_block: dict[str, float] = {}
        margin_balance = _clean(latest.get("margin_balance"))
        short_balance = _clean(latest.get("short_balance"))
        short_ratio = _clean(latest.get("short_ratio"))
        if margin_balance is not None:
            margin_block["margin_balance"] = margin_balance
        if short_balance is not None:
            margin_block["short_balance"] = short_balance
        if short_ratio is not None:
            margin_block["short_ratio"] = _round(short_ratio)
        if margin_block:
            summary["margin"] = margin_block

    stock_name = payload.get("stock_name") or symbol

    return QuantSummary(
        symbol=symbol, market=market, stock_name=stock_name, trade_date=trade_date,
        chart_period=period, chart_months=months,
        chart_start_date=_parse_date(payload.get("start_date")),
        chart_end_date=_parse_date(payload.get("end_date")),
        summary=summary,
    )
