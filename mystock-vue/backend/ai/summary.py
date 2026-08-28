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


def _at(series: Optional[list], idx: int):
    """series[idx]，series 為 None 或長度不足時回傳 None（避免每處都重複寫邊界判斷）。"""
    if not series or idx >= len(series):
        return None
    return series[idx]


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
    macd_data = payload.get("macd") or {}
    rsi_data = payload.get("rsi") or {}
    bollinger_data = payload.get("bollinger") or {}
    atr_data = payload.get("atr") or {}
    levels_data = payload.get("levels") or {}
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

    # MACD／RSI／布林通道／ATR：只讀 get_stock_chart_payload() 落地的結果，不得自行計算
    # （《AI 報告規格》§4.2 鐵則，見 Phase1-基礎量化與技術面 設計文件 §3.2、FR-P1-8）。
    dif_val = _clean(_at(macd_data.get("dif"), idx))
    if dif_val is not None:
        macd_block = {
            "dif": _round(dif_val),
            "signal": _round(_clean(_at(macd_data.get("signal"), idx))),
            "histogram": _round(_clean(_at(macd_data.get("histogram"), idx))),
        }
        macd_block = {k: v for k, v in macd_block.items() if v is not None}
        if macd_block:
            summary["macd"] = macd_block

    rsi_block: dict[str, float] = {}
    for rsi_period in rsi_data.get("periods") or []:
        val = _clean(_at(rsi_data.get(f"rsi_{rsi_period}"), idx))
        if val is not None:
            rsi_block[f"rsi_{rsi_period}"] = _round(val)
    if rsi_block:
        summary["rsi"] = rsi_block

    bb_upper = _clean(_at(bollinger_data.get("upper"), idx))
    if bb_upper is not None:
        bollinger_block = {
            "upper": _round(bb_upper),
            "middle": _round(_clean(_at(bollinger_data.get("middle"), idx))),
            "lower": _round(_clean(_at(bollinger_data.get("lower"), idx))),
            "bandwidth": _round(_clean(_at(bollinger_data.get("bandwidth"), idx))),
        }
        bollinger_block = {k: v for k, v in bollinger_block.items() if v is not None}
        if bollinger_block:
            summary["bollinger"] = bollinger_block

    atr_period = atr_data.get("period", 14)
    atr_val = _clean(_at(atr_data.get(f"atr_{atr_period}"), idx))
    if atr_val is not None:
        summary["atr"] = {f"atr_{atr_period}": _round(atr_val)}

    range_block: dict[str, Any] = {}
    highs = [r.get("high") for r in records if r.get("high")]
    lows = [r.get("low") for r in records if r.get("low")]
    if highs and lows:
        range_high, range_low = max(highs), min(lows)
        high_date = next((r["date"] for r in records if r.get("high") == range_high), None)
        low_date = next((r["date"] for r in records if r.get("low") == range_low), None)
        range_block.update({
            "high": _round(range_high), "high_date": high_date,
            "low": _round(range_low), "low_date": low_date,
        })

    # 固定 20／60 日高低點（FR-P1-6／FR-P1-8）：語意是「固定視窗位階」，與上面「本次圖表顯示
    # 區間高低」不同，兩者並存不互相取代（Phase1-基礎量化與技術面 設計文件 §9 Q-5）。
    for levels_window in levels_data.get("windows") or []:
        r_val = _clean(_at(levels_data.get(f"resistance_{levels_window}d"), idx))
        s_val = _clean(_at(levels_data.get(f"support_{levels_window}d"), idx))
        if r_val is not None:
            range_block[f"resistance_{levels_window}d"] = _round(r_val)
        if s_val is not None:
            range_block[f"support_{levels_window}d"] = _round(s_val)

    if range_block:
        summary["range"] = range_block

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
