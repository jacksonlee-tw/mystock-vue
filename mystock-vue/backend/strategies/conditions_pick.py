"""選股專用條件函式實作（選股功能與爬蟲 規格書 §5、§13；股價相對低點 需求規格書 §5）。

包含：
1. `valuation_filter`：本益比 (PE)、股價淨值比 (PB)、殖利率條件
2. `revenue_growth`：月營收年增率 (YoY)、月增率 (MoM) 成長條件
3. `chip_resonance`：外資與投信籌碼共振（連續買超、佔成交量比例）條件
4. `stock_pick_resonance`：基本面 + 籌碼面 + 技術面多因子共振選股條件
5. `relative_low_zone`：相對低點承接精選（估值 + 營收守衛 + 超跌狀態 + 籌碼洗盤 + 右側確認）

`stock_pick_resonance`／`relative_low_zone` 內部直接呼叫本檔既有的 `_eval_*` 私有判斷函式
做 AND 組合，不重複實作各面向的判斷邏輯（§5.5 鐵則／股價相對低點 規格書 ADR-RL-01）。
"""
from typing import Any, Dict, List, Optional

from indicators.chip import change_pct, consec_net_buy, cum_net, net_buy_days, net_buy_volume_ratio
from services.chip_provider import ScanContext
from strategies.registry import condition


def _eval_valuation_filter(ctx: ScanContext, idx: int, params: dict) -> Optional[dict]:
    """估值面判斷（PE 上下限、PB 上限、殖利率下限）。成立回傳 details，否則回傳 None。"""
    if not ctx.valuation:
        return None

    pe_max = params.get("pe_max")
    pe_min = params.get("pe_min")
    pb_max = params.get("pb_max")
    dividend_yield_min = params.get("dividend_yield_min")

    pe = ctx.valuation.get("pe_ratio", [None] * (idx + 1))[idx]
    pb = ctx.valuation.get("pb_ratio", [None] * (idx + 1))[idx]
    div_yield = ctx.valuation.get("dividend_yield", [None] * (idx + 1))[idx]

    # 1. 本益比檢查
    if pe_max is not None and (pe is None or pe > pe_max):
        return None
    if pe_min is not None and (pe is None or pe < pe_min):
        return None

    # 2. 股價淨值比檢查
    if pb_max is not None and (pb is None or pb > pb_max):
        return None

    # 3. 殖利率檢查
    if dividend_yield_min is not None and (div_yield is None or div_yield < dividend_yield_min):
        return None

    return {"pe_ratio": pe, "pb_ratio": pb, "dividend_yield": div_yield}


@condition(type="valuation_filter", min_bars=1, requires=("valuation",))
def valuation_filter(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """估值面篩選條件（PE 上下限、PB 上限、殖利率下限）。"""
    details = _eval_valuation_filter(ctx, idx, params)
    if details is None:
        return []
    return [{"direction": "pick_valuation", "details": details}]


def _eval_revenue_growth(ctx: ScanContext, idx: int, params: dict) -> Optional[dict]:
    """營收成長判斷（YoY 下限、MoM 下限、連續月數）。成立回傳 details，否則回傳 None。"""
    if not ctx.revenue_yoy:
        return None

    yoy_min = params.get("yoy_min", 0.0)
    mom_min = params.get("mom_min")
    consecutive = params.get("consecutive_months", 1)

    curr_yoy = ctx.revenue_yoy[idx]
    curr_mom = ctx.revenue_mom[idx] if ctx.revenue_mom else None
    vis_month = ctx.revenue_visible_month[idx] if ctx.revenue_visible_month else None

    if curr_yoy is None or curr_yoy < yoy_min:
        return None

    if mom_min is not None and (curr_mom is None or curr_mom < mom_min):
        return None

    # 若要求連續 N 個月成長，回溯檢查
    if consecutive > 1 and vis_month and ctx.revenue:
        sorted_months = sorted(ctx.revenue.keys())
        if vis_month in sorted_months:
            m_idx = sorted_months.index(vis_month)
            if m_idx + 1 < consecutive:
                return None
            check_months = sorted_months[m_idx - consecutive + 1 : m_idx + 1]
            for m in check_months:
                val = ctx.revenue[m].get("yoy_percent")
                if val is None or val < yoy_min:
                    return None

    return {"yoy_percent": curr_yoy, "mom_percent": curr_mom, "visible_month": vis_month}


@condition(type="revenue_growth", min_bars=2, requires=("revenue_yoy",))
def revenue_growth(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """營收成長篩選條件（YoY 下限、MoM 下限、連續月數）。"""
    details = _eval_revenue_growth(ctx, idx, params)
    if details is None:
        return []
    return [{"direction": "pick_revenue_growth", "details": details}]


def _eval_chip_resonance(ctx: ScanContext, idx: int, params: dict) -> Optional[dict]:
    """法人籌碼共振判斷（外資、投信連續買超或買超佔比）。成立回傳 details，否則回傳 None。"""
    foreign_consec = params.get("foreign_consec_days", 0)
    trust_consec = params.get("trust_consec_days", 0)
    foreign_ratio_min = params.get("foreign_net_ratio_min")
    trust_ratio_min = params.get("trust_net_ratio_min")
    window = params.get("window", 5)

    f_consec_actual = consec_net_buy(ctx.raw_records, "foreign_buy_sell", idx)
    t_consec_actual = consec_net_buy(ctx.raw_records, "trust_buy_sell", idx)

    if foreign_consec > 0 and f_consec_actual < foreign_consec:
        return None
    if trust_consec > 0 and t_consec_actual < trust_consec:
        return None

    f_ratio = None
    if foreign_ratio_min is not None:
        f_ratio = net_buy_volume_ratio(ctx.raw_records, "foreign_buy_sell", idx, window)
        if f_ratio is None or f_ratio < foreign_ratio_min:
            return None

    t_ratio = None
    if trust_ratio_min is not None:
        t_ratio = net_buy_volume_ratio(ctx.raw_records, "trust_buy_sell", idx, window)
        if t_ratio is None or t_ratio < trust_ratio_min:
            return None

    return {
        "foreign_consec_days": f_consec_actual,
        "trust_consec_days": t_consec_actual,
        "foreign_net_ratio": f_ratio,
        "trust_net_ratio": t_ratio,
        "foreign_cum_net_lots": cum_net(ctx.raw_records, "foreign_buy_sell", idx, window),
        "trust_cum_net_lots": cum_net(ctx.raw_records, "trust_buy_sell", idx, window),
    }


@condition(type="chip_resonance", min_bars=5, requires=("raw_records",))
def chip_resonance(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """法人籌碼共振篩選條件（外資、投信連續買超或買超佔比）。"""
    details = _eval_chip_resonance(ctx, idx, params)
    if details is None:
        return []
    return [{"direction": "pick_chip_resonance", "details": details}]


@condition(type="stock_pick_resonance", min_bars=25, requires=("valuation", "revenue_yoy", "raw_records"))
def stock_pick_resonance(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """多因子共振精選條件（估值 + 營收成長 + 籌碼買超 + 均線守護）。

    直接重用 `_eval_valuation_filter`/`_eval_revenue_growth`/`_eval_chip_resonance` 做 AND 組合，
    不複製各面向的判斷邏輯；籌碼門檻改用 `chip_window` 天的累計買超（indicators.chip.cum_net），
    而非只看當日單一筆淨買賣超。
    """
    valuation_details = _eval_valuation_filter(ctx, idx, {
        "pe_max": params.get("pe_max", 25.0),
        "pe_min": params.get("pe_min"),
        "pb_max": params.get("pb_max"),
        "dividend_yield_min": params.get("dividend_yield_min"),
    })
    if valuation_details is None:
        return []

    revenue_details = _eval_revenue_growth(ctx, idx, {
        "yoy_min": params.get("revenue_yoy_min", 10.0),
        "mom_min": params.get("revenue_mom_min"),
        "consecutive_months": params.get("revenue_consecutive_months", 1),
    })
    if revenue_details is None:
        return []

    # 籌碼門檻：外資 + 投信近 chip_window 日「累計」買超 > 0（非單日淨買賣超）
    chip_window = params.get("chip_window", 5)
    f_cum = cum_net(ctx.raw_records, "foreign_buy_sell", idx, chip_window)
    t_cum = cum_net(ctx.raw_records, "trust_buy_sell", idx, chip_window)
    if f_cum is None or t_cum is None or (f_cum + t_cum) <= 0:
        return []

    # 技術面守護：收盤價須站上指定均線（預設 MA20），只讀 ctx.ma，不自算
    ma_period = params.get("above_ma_period", 20)
    ma_val = ctx.ma.get(ma_period, [None] * (idx + 1))[idx]
    close = ctx.closes[idx]
    if ma_val is not None and close is not None and close < ma_val:
        return []

    return [{
        "direction": "pick_resonance",
        "details": {
            "close": close,
            f"ma{ma_period}": ma_val,
            **valuation_details,
            **revenue_details,
            "institutional_cum_net_lots": f_cum + t_cum,
        },
    }]


def _eval_oversold_window(series: List[Optional[float]], idx: int, lookback_days: int, threshold: float) -> Optional[float]:
    """近 lookback_days 日（含當日）序列是否「曾經」達到門檻（狀態式，非既有 bias/kd_cross
    條件的跨越式語意 —— 股價相對低點 需求規格書 §2.2-4）。BIAS／KD 皆是「值越低代表越超跌／
    超賣」，故統一取窗內最小值與門檻比較；未達門檻或資料不足回傳 None，達門檻回傳窗內最小值。
    供 C3（季線負乖離）與 C4（KD 超賣）共用，亦供 P1 其餘「近 N 日曾達門檻」條件重用（§5.2）。
    """
    start = max(0, idx - lookback_days + 1)
    window = [v for v in series[start:idx + 1] if v is not None]
    if not window:
        return None
    extreme = min(window)
    return extreme if extreme <= threshold else None


@condition(
    type="relative_low_zone",
    min_bars=60,
    requires=("valuation", "revenue_yoy", "raw_records", "kd"),
)
def relative_low_zone(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """相對低點承接精選（股價相對低點 需求規格書 §4.2、§5.2）：
    C1 估值低檔 + C2 基本面守衛 + C3 超跌狀態(BIAS60) + C4 動能超賣(KD) + C5 籌碼洗盤
    + C6 右側止跌確認，六項全部 AND 成立才觸發（ADR-RL-01：AND 寫在單一複合條件內）。
    C1/C2 直接重用既有 `_eval_valuation_filter`/`_eval_revenue_growth`，不重複實作
    （《策略架構》§9 鐵則）；短路順序把過濾力最強、成本最低的 C1 放最前（規格 AC-8）。
    """
    # C1 估值低檔
    valuation_details = _eval_valuation_filter(ctx, idx, {
        "pe_max": params.get("pe_max", 15.0),
        "pe_min": params.get("pe_min", 0.1),
        "pb_max": params.get("pb_max", 1.5),
        "dividend_yield_min": params.get("dividend_yield_min", 4.0),
    })
    if valuation_details is None:
        return []

    # C2 基本面守衛（避開價值陷阱；point-in-time 由 _eval_revenue_growth 內共用規則保證）
    revenue_details = _eval_revenue_growth(ctx, idx, {
        "yoy_min": params.get("revenue_yoy_min", 0.0),
        "consecutive_months": params.get("revenue_consecutive_months", 2),
    })
    if revenue_details is None:
        return []

    # C3 超跌狀態：近 N 日內曾出現 BIAS(ma_period) ≤ 門檻（狀態式，只讀 ctx.bias，不自算）
    bias_period = params.get("bias_ma_period", 60)
    bias_series = ctx.bias.get(bias_period)
    if not bias_series:
        return []
    bias_min = _eval_oversold_window(
        bias_series, idx,
        params.get("bias_lookback_days", 10),
        params.get("bias_max", -15.0),
    )
    if bias_min is None:
        return []

    # C4 動能超賣：近 N 日內曾出現 K ≤ 門檻（狀態式，只讀 ctx.kd，不自算；取代 v1.0 的 RSI）
    kd_key = tuple(params.get("kd_params", (9, 3, 3)))
    kd_series = ctx.kd.get(kd_key)
    if not kd_series:
        return []
    k_min = _eval_oversold_window(
        kd_series.k, idx,
        params.get("kd_lookback_days", 10),
        params.get("kd_oversold", 20),
    )
    if k_min is None:
        return []

    # C5 籌碼洗盤：融資 N 日變動 ≤ 門檻（浮額清洗）+ 外資或投信 N 日內至少 M 日淨買超
    margin_change = change_pct(
        ctx.raw_records, "margin_balance", idx, params.get("margin_change_window", 10),
    )
    if margin_change is None or margin_change > params.get("margin_change_max_pct", -5.0):
        return []
    inst_window = params.get("institutional_window", 5)
    min_buy_days = params.get("institutional_min_buy_days", 3)
    foreign_days = net_buy_days(ctx.raw_records, "foreign_buy_sell", idx, inst_window)
    trust_days = net_buy_days(ctx.raw_records, "trust_buy_sell", idx, inst_window)
    foreign_ok = foreign_days is not None and foreign_days >= min_buy_days
    trust_ok = trust_days is not None and trust_days >= min_buy_days
    if not foreign_ok and not trust_ok:
        return []

    # C6 右側止跌確認（必要條件，不得降級為濾網 —— ADR-RL-03）：
    # 收盤價站上月線 且 量能達 N 倍 5 日均量
    ma_period = params.get("above_ma_period", 20)
    ma_series = ctx.ma.get(ma_period)
    ma_val = ma_series[idx] if ma_series else None
    close = ctx.closes[idx]
    if close is None or ma_val is None or close < ma_val:
        return []
    volume_multiple = params.get("volume_multiple", 1.5)
    vol = ctx.volumes[idx]
    vol_ma = ctx.volume_ma[idx] if ctx.volume_ma else None
    if vol is None or not vol_ma or vol < vol_ma * volume_multiple:
        return []
    volume_ratio = vol / vol_ma

    return [{
        "direction": "pick_relative_low",
        "details": {
            "close": close,
            **valuation_details,
            **revenue_details,
            "bias_percent": bias_series[idx],
            "bias_min_in_window": bias_min,
            "kd_k_min_in_window": k_min,
            "margin_change_pct": round(margin_change, 2),
            "foreign_buy_days": foreign_days,
            "trust_buy_days": trust_days,
            "ma_period": ma_period,
            "ma_value": ma_val,
            "volume_ratio": round(volume_ratio, 2),
        },
    }]
