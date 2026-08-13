"""均線策略警示系統 設計文件第 2 節：六種均線觸發條件的實作。

每個條件函式簽章統一為 (ctx: ScanContext, idx: int, params: dict) -> List[dict]，
idx 是「當日」在 ctx.dates/ctx.closes/... 上的索引；回傳一份訊號列表（可能為空、也可能
一天觸發多筆，例如同時穿越月線與季線）。訊號 dict 至少含 direction 與 details。

所有均線／乖離率一律只讀 ctx.ma / ctx.bias（indicators/moving_average.py 預先算好的結果），
不在這裡自己加減乘除或重算均線（策略管理架構 設計文件第 9 節鐵則）；
遇到 None（資料不足）一律跳過該筆判斷，不拋例外（滿足 NF-2）。
"""
from typing import List

from services.chip_provider import ScanContext
from strategies.registry import condition


def _is_aligned(ctx: ScanContext, idx: int, periods: List[int], bullish: bool, require_slope: bool) -> bool:
    if idx < 0:
        return False
    values = []
    for p in periods:
        series = ctx.ma.get(p)
        if not series or series[idx] is None:
            return False
        values.append(series[idx])

    seq = values if bullish else list(reversed(values))
    if not all(seq[i] > seq[i + 1] for i in range(len(seq) - 1)):
        return False

    if require_slope:
        if idx < 1:
            return False
        for p, curr in zip(periods, values):
            prev = ctx.ma[p][idx - 1]
            if prev is None:
                return False
            slope = curr - prev
            if bullish and slope <= 0:
                return False
            if not bullish and slope >= 0:
                return False

    return True


@condition(type="price_cross", min_bars=2)
def price_cross(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """收盤價突破/跌破關鍵均線（均線策略警示系統 設計文件第 2.1 節）。"""
    if idx < 1:
        return []
    close, prev_close = ctx.closes[idx], ctx.closes[idx - 1]
    if close is None or prev_close is None:
        return []

    periods = params.get("ma_periods", [])
    allowed = set(params.get("directions", ["cross_above", "cross_under"]))
    results = []
    for p in periods:
        series = ctx.ma.get(p)
        if not series:
            continue
        ma_now, ma_prev = series[idx], series[idx - 1]
        if ma_now is None or ma_prev is None:
            continue

        bias_now = ctx.bias.get(p, [None] * ctx.length)[idx]
        details = {"close": close, "ma_period": p, "ma_value": ma_now, "bias_percent": bias_now}

        if "cross_above" in allowed and prev_close < ma_prev and close > ma_now:
            results.append({"direction": f"cross_above_MA{p}", "details": details})
        if "cross_under" in allowed and prev_close > ma_prev and close < ma_now:
            results.append({"direction": f"cross_under_MA{p}", "details": details})
    return results


@condition(type="ma_cross", min_bars=2)
def ma_cross(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """均線黃金交叉 / 死亡交叉（均線策略警示系統 設計文件第 2.1 節）。"""
    if idx < 1:
        return []

    results = []
    for pair in params.get("pairs", []):
        short_p, long_p = pair.get("short"), pair.get("long")
        short_series, long_series = ctx.ma.get(short_p), ctx.ma.get(long_p)
        if not short_series or not long_series:
            continue
        s_now, l_now = short_series[idx], long_series[idx]
        s_prev, l_prev = short_series[idx - 1], long_series[idx - 1]
        if None in (s_now, l_now, s_prev, l_prev):
            continue

        details = {"short_period": short_p, "long_period": long_p, "short_ma": s_now, "long_ma": l_now}
        if s_prev <= l_prev and s_now > l_now:
            results.append({"direction": f"golden_cross_{short_p}_{long_p}", "details": details})
        elif s_prev >= l_prev and s_now < l_now:
            results.append({"direction": f"death_cross_{short_p}_{long_p}", "details": details})
    return results


@condition(type="alignment", min_bars=2)
def alignment(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """均線多頭排列 / 空頭排列，僅在「由非排列轉為排列」的當天觸發（均線策略警示系統 設計文件第 2.2 節）。"""
    periods = params.get("ma_periods", [])
    require_slope = params.get("require_slope", False)
    if idx < 1 or len(periods) < 2:
        return []

    results = []
    for bullish, direction in ((True, "bullish_alignment"), (False, "bearish_alignment")):
        now = _is_aligned(ctx, idx, periods, bullish, require_slope)
        prev = _is_aligned(ctx, idx - 1, periods, bullish, require_slope)
        if now and not prev:
            results.append({
                "direction": direction,
                "details": {
                    "close": ctx.closes[idx],
                    "ma_periods": periods,
                    "values": {f"MA{p}": ctx.ma[p][idx] for p in periods},
                },
            })
    return results


@condition(type="squeeze_breakout", min_bars=30)
def squeeze_breakout(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """均線糾結突破：過去 N 天四線極差持續小於門檻，當日收盤突破最上方均線
    （均線策略警示系統 設計文件第 2.3 節）。量能/K棒品質交給選配濾網（filters.py）處理。"""
    periods = params.get("ma_periods", [])
    threshold = params.get("squeeze_threshold", 0.02)
    min_days = params.get("squeeze_min_days", 5)
    if idx < min_days or not periods:
        return []

    close = ctx.closes[idx]
    if close is None:
        return []

    today_values = [ctx.ma.get(p, [None] * ctx.length)[idx] for p in periods]
    if any(v is None for v in today_values):
        return []
    upper = max(today_values)
    if close <= upper:
        return []

    for j in range(idx - min_days, idx):
        c = ctx.closes[j]
        if c is None or c == 0:
            return []
        values = [ctx.ma.get(p, [None] * ctx.length)[j] for p in periods]
        if any(v is None for v in values):
            return []
        if (max(values) - min(values)) / c >= threshold:
            return []

    return [{
        "direction": "squeeze_breakout",
        "details": {"close": close, "upper_ma": upper, "ma_periods": periods, "squeeze_min_days": min_days},
    }]


@condition(type="bias", min_bars=2)
def bias(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """正/負乖離過大，僅在「跨越門檻」的當天觸發（均線策略警示系統 設計文件第 2.4 節）。"""
    if idx < 1:
        return []

    period = params.get("ma_period")
    series = ctx.bias.get(period)
    if not series:
        return []
    curr, prev = series[idx], series[idx - 1]
    if curr is None or prev is None:
        return []

    overbought = params.get("overbought_threshold")
    oversold = params.get("oversold_threshold")
    close = ctx.closes[idx]
    ma_value = ctx.ma.get(period, [None] * ctx.length)[idx]

    results = []
    if overbought is not None and curr >= overbought and prev < overbought:
        results.append({
            "direction": "overbought",
            "details": {"close": close, "ma_period": period, "ma_value": ma_value, "bias_percent": curr},
        })
    if oversold is not None and curr <= oversold and prev > oversold:
        results.append({
            "direction": "oversold",
            "details": {"close": close, "ma_period": period, "ma_value": ma_value, "bias_percent": curr},
        })
    return results


@condition(type="pullback", min_bars=20)
def pullback(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """均線回踩測試：先確認過去 N 天站穩均線之上，再檢查當日拉回至均線附近但未跌破
    （均線策略警示系統 設計文件第 2.4 節）。"""
    periods = params.get("ma_periods", [])
    proximity = params.get("proximity_percent", 1.0)
    lookback = params.get("trend_lookback_days", 20)
    if idx < lookback or not periods:
        return []

    close = ctx.closes[idx]
    if close is None:
        return []

    results = []
    for p in periods:
        series = ctx.ma.get(p)
        if not series:
            continue
        ma_now = series[idx]
        if ma_now is None or ma_now == 0:
            continue

        trend_ok = True
        for j in range(idx - lookback, idx):
            c, m = ctx.closes[j], series[j]
            if c is None or m is None or c <= m:
                trend_ok = False
                break
        if not trend_ok:
            continue

        distance_pct = abs(close - ma_now) / ma_now * 100
        not_broken = close >= ma_now * (1 - proximity / 100)
        if distance_pct <= proximity and not_broken:
            results.append({
                "direction": f"pullback_support_MA{p}",
                "details": {"close": close, "ma_period": p, "ma_value": ma_now, "distance_percent": round(distance_pct, 2)},
            })
    return results
