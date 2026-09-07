"""策略規則人話說明（供 /api/v1/strategies 使用；策略選股與風控中心 前台策略說明資料化）。

說明文字一律從 strategy.conditions / strategy.filters 的實際參數動態組裝，不寫死具體數字，
YAML 改門檻時說明文字自動同步，避免像前端曾經寫死的策略陣列那樣過時或漏同步新策略。
"""
from typing import Any, Callable, Dict, List

from strategies.config_loader import StrategyDef

_ZONE_RULE_LABEL = {"both": "任一端", "oversold_only": "僅超賣", "overbought_only": "僅超買"}


def _kd_label(params: List[int]) -> str:
    return ",".join(str(p) for p in params)


def _explain_price_cross(p: dict) -> str:
    periods = "、".join(f"MA{n}" for n in p.get("ma_periods", []))
    return f"收盤價向上突破或向下跌破 {periods} 任一條均線"


def _explain_ma_cross(p: dict) -> str:
    pairs = "、".join(f"{pair.get('short')}日/{pair.get('long')}日" for pair in p.get("pairs", []))
    return f"短均線與長均線交叉（{pairs}），黃金交叉偏多、死亡交叉偏空"


def _explain_alignment(p: dict) -> str:
    periods = "、".join(f"MA{n}" for n in p.get("ma_periods", []))
    slope = "，且須同時符合斜率方向" if p.get("require_slope") else ""
    return f"{periods} 依大小排列成多頭或空頭排列{slope}"


def _explain_squeeze_breakout(p: dict) -> str:
    periods = "、".join(f"MA{n}" for n in p.get("ma_periods", []))
    pct = p.get("squeeze_threshold", 0) * 100
    return f"{periods} 糾結（極差 < 股價 × {pct:g}%）達 {p.get('squeeze_min_days')} 天後帶量突破"


def _explain_bias(p: dict) -> str:
    return (
        f"收盤價與 MA{p.get('ma_period')} 的乖離率 ≥{p.get('overbought_threshold')}% 視為超買，"
        f"≤{p.get('oversold_threshold')}% 視為超賣"
    )


def _explain_pullback(p: dict) -> str:
    periods = "、".join(f"MA{n}" for n in p.get("ma_periods", []))
    return f"近 {p.get('trend_lookback_days')} 天持續站上 {periods}，且股價回踩至均線 ±{p.get('proximity_percent')}% 範圍內未跌破"


def _explain_chip_bottom_turnover(p: dict) -> str:
    return (
        f"近 {p.get('lookback_below_days')} 天內曾跌破 MA{p.get('ma_period')}，"
        f"融資餘額近 {p.get('margin_change_window')} 天減少 ≥{abs(p.get('margin_change_max_pct', 0))}%，"
        f"且外資或投信近 {p.get('institutional_window')} 天內連續買超 ≥{p.get('consec_buy_days')} 天"
    )


def _explain_chip_short_squeeze(p: dict) -> str:
    return (
        f"MA{p.get('ma_period')} 近 {p.get('ma_slope_window')} 天轉為上揚，"
        f"三大法人近 {p.get('institutional_window')} 天內買超 ≥{p.get('institutional_min_buy_days')} 天，"
        f"券資比 ≥{p.get('short_margin_ratio_min_pct')}%（達近 {p.get('short_margin_ratio_percentile_window')} 天第 "
        f"{p.get('short_margin_ratio_percentile')} 百分位），且融券餘額近 {p.get('short_change_window')} 天暴增 "
        f"≥{p.get('short_change_min_pct')}%"
    )


def _explain_chip_distribution_top(p: dict) -> str:
    return (
        f"三大法人連續賣超 ≥{p.get('consec_sell_days')} 天，"
        f"且融資餘額創近 {p.get('margin_high_window')} 天新高（跌破 MA{p.get('ma_period')} 時風險更高）"
    )


def _explain_kd_cross(p: dict) -> str:
    zone = _ZONE_RULE_LABEL.get(p.get("zone_rule"), p.get("zone_rule"))
    guard = p.get("trend_guard") or {}
    guard_txt = f"，且須站上 MA{guard.get('ma_period')} 才視為有效" if guard.get("mode") == "require_above" else ""
    return (
        f"K/D({_kd_label(p.get('kd_params', []))}) 交叉，超賣 ≤{p.get('oversold_threshold')}、"
        f"超買 ≥{p.get('overbought_threshold')}（判定範圍：{zone}）{guard_txt}"
    )


def _explain_macd_cross(p: dict) -> str:
    directions = "、".join(p.get("directions", []))
    return f"MACD({_kd_label(p.get('macd_params', []))}) 出現 {directions}"


def _explain_rsi_zone(p: dict) -> str:
    directions = "、".join(p.get("directions", []))
    return f"RSI({p.get('rsi_period')}) 由超賣 ≤{p.get('oversold_threshold')} 回升，或由超買 ≥{p.get('overbought_threshold')} 回落（{directions}）"


def _explain_revenue_yoy_decline(p: dict) -> str:
    return f"月營收年增率連續 {p.get('consecutive_months')} 個月低於 {p.get('yoy_threshold')}%"


def _explain_valuation_filter(p: dict) -> str:
    parts = []
    if p.get("pe_max") is not None:
        parts.append(f"本益比 ≤{p['pe_max']}")
    if p.get("pe_min") is not None:
        parts.append(f"本益比 ≥{p['pe_min']}")
    if p.get("pb_max") is not None:
        parts.append(f"股價淨值比 ≤{p['pb_max']}")
    if p.get("dividend_yield_min") is not None:
        parts.append(f"殖利率 ≥{p['dividend_yield_min']}%")
    return "、".join(parts) or "無估值門檻"


def _explain_revenue_growth(p: dict) -> str:
    parts = [f"月營收年增率 ≥{p.get('yoy_min', 0)}%"]
    if p.get("mom_min") is not None:
        parts.append(f"月增率 ≥{p['mom_min']}%")
    consecutive = p.get("consecutive_months", 1)
    if consecutive > 1:
        parts.append(f"連續 {consecutive} 個月符合")
    return "、".join(parts)


def _explain_chip_resonance(p: dict) -> str:
    parts = []
    if p.get("foreign_consec_days"):
        parts.append(f"外資連續買超 ≥{p['foreign_consec_days']} 天")
    if p.get("trust_consec_days"):
        parts.append(f"投信連續買超 ≥{p['trust_consec_days']} 天")
    window = p.get("window", 5)
    if p.get("foreign_net_ratio_min") is not None:
        parts.append(f"外資買超佔近 {window} 日均量 ≥{p['foreign_net_ratio_min']}%")
    if p.get("trust_net_ratio_min") is not None:
        parts.append(f"投信買超佔近 {window} 日均量 ≥{p['trust_net_ratio_min']}%")
    return "、".join(parts) or "無籌碼門檻"


def _explain_stock_pick_resonance(p: dict) -> str:
    return (
        f"本益比 ≤{p.get('pe_max', 25.0)}、月營收年增率 ≥{p.get('revenue_yoy_min', 10.0)}%、"
        f"外資與投信近 {p.get('chip_window', 5)} 天累計買超為正，且收盤價站上 MA{p.get('above_ma_period', 20)}"
    )


def _explain_relative_low_zone(p: dict) -> str:
    return (
        f"六項條件同時成立：① 本益比 ≤{p.get('pe_max', 15.0)}／殖利率 ≥{p.get('dividend_yield_min', 4.0)}%；"
        f"② 月營收年增率 ≥{p.get('revenue_yoy_min', 0.0)}%（連續 {p.get('revenue_consecutive_months', 2)} 個月）；"
        f"③ 近 {p.get('bias_lookback_days', 10)} 天內 MA{p.get('bias_ma_period', 60)} 乖離率曾 ≤{p.get('bias_max', -15.0)}%；"
        f"④ 近 {p.get('kd_lookback_days', 10)} 天內 K 值曾 ≤{p.get('kd_oversold', 20)}；"
        f"⑤ 融資餘額近 {p.get('margin_change_window', 10)} 天減少 ≥{abs(p.get('margin_change_max_pct', -5.0))}% "
        f"且法人近 {p.get('institutional_window', 5)} 天內買超 ≥{p.get('institutional_min_buy_days', 3)} 天；"
        f"⑥ 帶量（≥{p.get('volume_multiple', 1.5)} 倍均量）站回 MA{p.get('above_ma_period', 20)}"
    )


def _explain_eps_filter(p: dict) -> str:
    parts = []
    if p.get("eps_min") is not None:
        parts.append(f"最新已公開季報 EPS ≥{p['eps_min']}")
    if p.get("eps_positive"):
        parts.append("且須為正值（獲利）")
    return "、".join(parts) or "無 EPS 門檻"


def _explain_trailing_stop(p: dict) -> str:
    return f"股價自持股期間最高點回檔 ≥{p.get('drawdown_pct')}%"


def _explain_fixed_stop_loss(p: dict) -> str:
    return f"股價低於平均持股成本 ≥{p.get('stop_loss_pct')}%"


def _explain_time_stop(p: dict) -> str:
    return f"持有超過 {p.get('max_holding_days')} 個交易日且報酬率未達 {p.get('min_return_pct')}%"


_CONDITION_EXPLAINERS: Dict[str, Callable[[dict], str]] = {
    "price_cross": _explain_price_cross,
    "ma_cross": _explain_ma_cross,
    "alignment": _explain_alignment,
    "squeeze_breakout": _explain_squeeze_breakout,
    "bias": _explain_bias,
    "pullback": _explain_pullback,
    "chip_bottom_turnover": _explain_chip_bottom_turnover,
    "chip_short_squeeze": _explain_chip_short_squeeze,
    "chip_distribution_top": _explain_chip_distribution_top,
    "kd_cross": _explain_kd_cross,
    "macd_cross": _explain_macd_cross,
    "rsi_zone": _explain_rsi_zone,
    "revenue_yoy_decline": _explain_revenue_yoy_decline,
    "valuation_filter": _explain_valuation_filter,
    "revenue_growth": _explain_revenue_growth,
    "chip_resonance": _explain_chip_resonance,
    "stock_pick_resonance": _explain_stock_pick_resonance,
    "relative_low_zone": _explain_relative_low_zone,
    "eps_filter": _explain_eps_filter,
    "trailing_stop": _explain_trailing_stop,
    "fixed_stop_loss": _explain_fixed_stop_loss,
    "time_stop": _explain_time_stop,
}

_FILTER_EXPLAINERS: Dict[str, Callable[[dict], str]] = {
    "volume_confirm": lambda p: f"成交量達 {p.get('multiple')} 倍均量",
    "candlestick_confirm": lambda p: f"K 棒實體比例 ≥{p.get('body_ratio')}",
    "institutional_buy": lambda p: f"近 {p.get('lookback_days')} 天三大法人買超",
}


def explain_conditions(strategy: StrategyDef) -> List[str]:
    """回傳每個 condition 的人話規則說明；缺對應 explainer 時退回顯示原始參數，不讓整段消失。"""
    lines = []
    for cond in strategy.conditions:
        cond_type = cond.get("type")
        explainer = _CONDITION_EXPLAINERS.get(cond_type)
        if explainer:
            try:
                lines.append(explainer(cond))
                continue
            except Exception:
                pass
        lines.append(f"{cond_type}：{cond}")
    return lines


def explain_filters(strategy: StrategyDef) -> List[str]:
    """濾網只影響 signal_strength（強弱標籤），不影響是否觸發，呼叫端顯示時應附註此點。"""
    lines = []
    for f in strategy.filters:
        f_type = f.get("type")
        params = f.get("params", {})
        explainer = _FILTER_EXPLAINERS.get(f_type)
        if explainer:
            try:
                lines.append(explainer(params))
                continue
            except Exception:
                pass
        lines.append(f"{f_type}：{params}")
    return lines
