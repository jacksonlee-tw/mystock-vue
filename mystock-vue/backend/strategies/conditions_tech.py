"""均線策略警示系統 設計文件第 2 節：六種均線觸發條件的實作。

每個條件函式簽章統一為 (ctx: ScanContext, idx: int, params: dict) -> List[dict]，
idx 是「當日」在 ctx.dates/ctx.closes/... 上的索引；回傳一份訊號列表（可能為空、也可能
一天觸發多筆，例如同時穿越月線與季線）。訊號 dict 至少含 direction 與 details。

所有均線／乖離率一律只讀 ctx.ma / ctx.bias（indicators/moving_average.py 預先算好的結果），
不在這裡自己加減乘除或重算均線（策略管理架構 設計文件第 9 節鐵則）；
遇到 None（資料不足）一律跳過該筆判斷，不拋例外（滿足 NF-2）。
"""
import logging
from typing import List, Optional

from services.chip_provider import KDSeries, ScanContext
from strategies.registry import condition

logger = logging.getLogger("mystock-backend")


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


# ══ KD 隨機指標（KD指標 設計規格書 §5.2）══════════════════════════════════
# directions 參數值 → (完整 direction 字串, 是否為黃金交叉, 對應區間)。
# 只支援區間限定的兩個方向——一般區（中間區）交叉刻意不支援（決議 D3：KD 在中間區的交叉
# 極其頻繁，開放會直接淹沒警示看板；見 KD指標 設計規格書 §12 D3）。
_KD_DIRECTION_MAP = {
    "golden_cross_oversold": ("kd_golden_cross_oversold", True, "oversold"),
    "death_cross_overbought": ("kd_death_cross_overbought", False, "overbought"),
}
_DEFAULT_KD_DIRECTIONS = ["golden_cross_oversold", "death_cross_overbought"]

# 未知 directions 值 / 未登記在 ma_periods 的 trend_guard.ma_period，各自只記一次警告，
# 避免同一個問題在逐標的、逐日的迴圈中洗版 log（比照 strategies/filters.py 的既有作法）。
_warned_kd_direction: set = set()
_warned_kd_trend_ma: set = set()


def _kd_zone_ok(zone_rule: str, k: float, d: float, in_zone) -> bool:
    """zone_rule 決定交叉點要滿足哪種區間條件（KD指標 設計規格書 §5.2 參數表）。"""
    if zone_rule == "k_only":
        return in_zone(k)
    if zone_rule == "either":
        return in_zone(k) or in_zone(d)
    return in_zone(k) and in_zone(d)  # "both"（預設）


def _trend_guard(ctx: ScanContext, idx: int, guard: Optional[dict]) -> Optional[dict]:
    """趨勢守衛（KD指標 設計規格書 §5.4）。回傳 None 代表未通過，訊號整筆擋掉；
    回傳 dict（可能為空）代表通過，內容併入 details（key 沿用既有 MA 條件慣用的
    ma_period／ma_value，讓 scanner._suggested_action() 不需另外改讀取邏輯）。
    只能讀 ctx.ma[period]，不得自行計算均線（策略管理架構 設計文件第 9 節鐵則）。

    原僅供 kd_cross 使用（故舊名 _kd_trend_guard），邏輯本身與 KD 無關，只是讀 ctx.ma，
    Phase1-基礎量化與技術面 設計文件 §9 Q-1 新增 macd_cross／rsi_zone 後一併共用，
    避免同一段「收盤價相對某均線」判斷分散成三份幾乎相同的程式碼。"""
    if not guard:
        return {}
    mode = guard.get("mode", "off")
    if mode == "off":
        return {}

    ma_period = guard.get("ma_period")
    series = ctx.ma.get(ma_period)
    if not series:
        if ma_period not in _warned_kd_trend_ma:
            logger.warning(f"[策略引擎] kd_cross 的 trend_guard.ma_period={ma_period} 不在 ma_periods 設定內，已略過")
            _warned_kd_trend_ma.add(ma_period)
        return None

    ma_value = series[idx]
    close = ctx.closes[idx]
    if ma_value is None or close is None:
        return None
    if mode == "require_above" and close <= ma_value:
        return None
    if mode == "require_below" and close >= ma_value:
        return None
    return {"ma_period": ma_period, "ma_value": ma_value}


def _kd_is_blunted(series: KDSeries, idx: int, window: int, zone: str, threshold: float) -> bool:
    """鈍化判定（KD指標 設計規格書 §5.4）：交叉發生前 window 根內，K 值持續位於同側極端區
    ——死亡交叉看 K > overbought_threshold、黃金交叉看 K < oversold_threshold（嚴格不等式）。
    視窗內任一根缺值視為「無法判斷」，保守回傳未鈍化。"""
    if idx - window < 0:
        return False
    for j in range(idx - window, idx):
        k_j = series.k[j]
        if k_j is None:
            return False
        if zone == "overbought" and k_j <= threshold:
            return False
        if zone == "oversold" and k_j >= threshold:
            return False
    return True


@condition(type="kd_cross", min_bars=35, requires=("kd",))
def kd_cross(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """KD 超賣區黃金交叉 / 超買區死亡交叉（KD指標 設計規格書 §5.2）。

    min_bars=35：RSV 9 根 + 暖身 25 根 + 交叉需回看 1 根（同設計規格書 §3.3 誤差推導）。
    只讀 ctx.kd（indicators/stochastic.py 預先算好的結果），不在這裡重算 KD。
    """
    if idx < 1:
        return []

    kd_params = tuple(params.get("kd_params", (9, 3, 3)))
    series = ctx.kd.get(kd_params)
    if series is None:
        return []

    k_now, k_prev = series.k[idx], series.k[idx - 1]
    d_now, d_prev = series.d[idx], series.d[idx - 1]
    if None in (k_now, k_prev, d_now, d_prev):
        return []

    golden = k_prev <= d_prev and k_now > d_now
    death = k_prev >= d_prev and k_now < d_now
    if not golden and not death:
        return []

    oversold = params.get("oversold_threshold", 20)
    overbought = params.get("overbought_threshold", 80)
    zone_rule = params.get("zone_rule", "both")

    directions_wanted = []
    for value in params.get("directions", _DEFAULT_KD_DIRECTIONS):
        if value not in _KD_DIRECTION_MAP:
            if value not in _warned_kd_direction:
                logger.warning(f"[策略引擎] kd_cross 不支援的 directions 值，已略過: {value}")
                _warned_kd_direction.add(value)
            continue
        directions_wanted.append(value)

    close = ctx.closes[idx]
    blunt_guard = params.get("blunt_guard")
    results = []

    for value in directions_wanted:
        direction, is_golden, zone = _KD_DIRECTION_MAP[value]
        if is_golden != golden:
            continue

        threshold = oversold if zone == "oversold" else overbought
        in_zone = (lambda v, t=threshold: v <= t) if zone == "oversold" else (lambda v, t=threshold: v >= t)
        if not _kd_zone_ok(zone_rule, k_now, d_now, in_zone):
            continue

        trend_extra = _trend_guard(ctx, idx, params.get("trend_guard"))
        if trend_extra is None:
            continue  # 趨勢守衛未通過，訊號整筆擋掉（非缺值容錯，是策略層的刻意過濾）

        blunted = False
        if blunt_guard:
            blunt_mode = blunt_guard.get("mode", "downgrade")
            if blunt_mode != "off":
                blunted = _kd_is_blunted(series, idx, blunt_guard.get("window", 5), zone, threshold)
                if blunted and blunt_mode == "suppress":
                    continue

        details = {
            "k": k_now, "d": d_now, "k_prev": k_prev, "d_prev": d_prev,
            "close": close, "kd_params": list(kd_params),
            "zone": zone, "threshold": threshold, "blunted": blunted,
            **trend_extra,
        }
        results.append({"direction": direction, "details": details})

    return results


# ══ MACD（Phase1-基礎量化與技術面 設計文件 §9 Q-1）══════════════════════════
# min_bars=40：slow_period(26) + signal_period(9) 暖身 + 前一日比較 1 根，抓寬一點的安全邊際
# （比照 kd_cross 的 min_bars=35 同樣抓「理論最短暖身 + 1」的作法）。

@condition(type="macd_cross", min_bars=40, requires=("macd",))
def macd_cross(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """MACD 黃金交叉 / 死亡交叉：DIF 上穿／下穿訊號線（Phase1-基礎量化與技術面 設計文件 §9 Q-1）。

    只讀 ctx.macd（indicators/macd.py 預先算好、經 stock_service 全歷史計算後切片的結果，
    見該設計文件 §3.3），不在此重算 EMA 或 DIF（策略管理架構 設計文件第 9 節鐵則）。
    """
    if idx < 1:
        return []

    macd_params = tuple(params.get("macd_params", (12, 26, 9)))
    series = ctx.macd.get(macd_params)
    if series is None:
        return []

    dif_now, dif_prev = series.dif[idx], series.dif[idx - 1]
    sig_now, sig_prev = series.signal[idx], series.signal[idx - 1]
    if None in (dif_now, dif_prev, sig_now, sig_prev):
        return []

    golden = dif_prev <= sig_prev and dif_now > sig_now
    death = dif_prev >= sig_prev and dif_now < sig_now
    if not golden and not death:
        return []

    directions_wanted = set(params.get("directions", ["golden_cross", "death_cross"]))
    close = ctx.closes[idx]
    details_base = {
        "close": close, "dif": dif_now, "signal": sig_now,
        "histogram": series.histogram[idx], "macd_params": list(macd_params),
    }

    results = []
    if golden and "golden_cross" in directions_wanted:
        trend_extra = _trend_guard(ctx, idx, params.get("trend_guard"))
        if trend_extra is not None:
            results.append({"direction": "macd_golden_cross", "details": {**details_base, **trend_extra}})
    if death and "death_cross" in directions_wanted:
        trend_extra = _trend_guard(ctx, idx, params.get("trend_guard"))
        if trend_extra is not None:
            results.append({"direction": "macd_death_cross", "details": {**details_base, **trend_extra}})

    return results


# ══ RSI（Phase1-基礎量化與技術面 設計文件 §9 Q-1／Q-3）══════════════════════
# 門檻採業界慣用 70/30（Q-3 決議，非 v1.0 草案的 80/20）。與 kd_cross 一樣採「跨越門檻的
# 當天觸發」而非「持續位於區間內每天都觸發」，避免同一段超賣／超買期間洗版警示看板。
# min_bars=20：預設 14 期 RSI 的 Wilder 暖身（period+1=15 根）+ 前一日比較，抓寬安全邊際。

@condition(type="rsi_zone", min_bars=20, requires=("rsi",))
def rsi_zone(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """RSI 超賣區止跌 / 超買區轉弱：RSI 由極端區間穿越回中性區（Phase1-基礎量化與技術面 設計文件 §9 Q-1）。

    只讀 ctx.rsi（indicators/rsi.py 預先算好、經 stock_service 全歷史計算後切片的結果，
    見該設計文件 §3.3），不在此重算漲跌幅或平均漲跌（策略管理架構 設計文件第 9 節鐵則）。
    """
    if idx < 1:
        return []

    period = params.get("rsi_period", 14)
    series = ctx.rsi.get(period)
    if not series:
        return []

    curr, prev = series[idx], series[idx - 1]
    if curr is None or prev is None:
        return []

    oversold = params.get("oversold_threshold", 30)
    overbought = params.get("overbought_threshold", 70)
    directions_wanted = set(params.get("directions", ["oversold_recovery", "overbought_reversal"]))
    close = ctx.closes[idx]

    results = []
    if "oversold_recovery" in directions_wanted and prev <= oversold and curr > oversold:
        trend_extra = _trend_guard(ctx, idx, params.get("trend_guard"))
        if trend_extra is not None:
            results.append({
                "direction": "rsi_oversold_recovery",
                "details": {
                    "close": close, "rsi": curr, "rsi_prev": prev,
                    "rsi_period": period, "threshold": oversold, **trend_extra,
                },
            })
    if "overbought_reversal" in directions_wanted and prev >= overbought and curr < overbought:
        trend_extra = _trend_guard(ctx, idx, params.get("trend_guard"))
        if trend_extra is not None:
            results.append({
                "direction": "rsi_overbought_reversal",
                "details": {
                    "close": close, "rsi": curr, "rsi_prev": prev,
                    "rsi_period": period, "threshold": overbought, **trend_extra,
                },
            })

    return results
