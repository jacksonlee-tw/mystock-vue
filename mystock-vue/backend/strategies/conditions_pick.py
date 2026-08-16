"""選股專用條件函式實作（選股功能與爬蟲 規格書 §5、§13）。

包含：
1. `valuation_filter`：本益比 (PE)、股價淨值比 (PB)、殖利率條件
2. `revenue_growth`：月營收年增率 (YoY)、月增率 (MoM) 成長條件
3. `chip_resonance`：外資與投信籌碼共振（連續買超、佔成交量比例）條件
4. `stock_pick_resonance`：基本面 + 籌碼面 + 技術面多因子共振選股條件

`stock_pick_resonance` 內部直接呼叫本檔 `_eval_valuation_filter`/`_eval_revenue_growth`/
`_eval_chip_resonance` 三個私有判斷函式做 AND 組合，不重複實作各面向的判斷邏輯（§5.5 鐵則）。
"""
from typing import Any, Dict, List, Optional

from indicators.chip import consec_net_buy, cum_net, net_buy_volume_ratio
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
