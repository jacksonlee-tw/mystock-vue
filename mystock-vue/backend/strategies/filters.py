"""濾網實作（均線策略警示系統 設計文件第 3 節）。

設計原則：濾網只做「加分」──計入 signal_strength 的通過項目，不會擋掉核心策略本身已觸發的
訊號（doc 8.3 節：warning 一定會產生，只是強度不同）。未知的濾網類型記一次警告即跳過，不中斷掃描。
"""
import logging
from typing import Any, Callable, Dict, List

from services.chip_provider import ScanContext

logger = logging.getLogger("mystock-backend")

FilterFunc = Callable[[ScanContext, int, dict], bool]


def volume_confirm(ctx: ScanContext, idx: int, params: dict) -> bool:
    """突破當天成交量 ≥ 前 N 日（不含當日）均量 × multiple。"""
    multiple = params.get("multiple", 1.5)
    window = params.get("window", 5)
    if idx < window:
        return False
    prior = ctx.volumes[idx - window:idx]
    if not prior or any(v is None for v in prior):
        return False
    avg = sum(prior) / len(prior)
    today = ctx.volumes[idx]
    if today is None or avg <= 0:
        return False
    return today >= avg * multiple


def candlestick_confirm(ctx: ScanContext, idx: int, params: dict) -> bool:
    """突破當天須為陽線，且實體長度 ≥ 振幅 × body_ratio，排除長上影線假突破。"""
    body_ratio = params.get("body_ratio", 0.5)
    o, c, h, l = ctx.opens[idx], ctx.closes[idx], ctx.highs[idx], ctx.lows[idx]
    if None in (o, c, h, l) or c <= o:
        return False
    price_range = h - l
    if price_range <= 0:
        return False
    return (c - o) / price_range >= body_ratio


def institutional_buy(ctx: ScanContext, idx: int, params: dict) -> bool:
    """觸發日前 N 天（含當日），外資＋投信呈現淨買超。僅台股適用（美股無三大法人資料）。"""
    if ctx.market != "tw":
        return False
    lookback = params.get("lookback_days", 3)
    start = max(0, idx - lookback + 1)
    total = 0
    for j in range(start, idx + 1):
        rec = ctx.raw_records[j]
        total += (rec.get("foreign_buy_sell") or 0) + (rec.get("trust_buy_sell") or 0)
    return total > 0


FILTER_REGISTRY: Dict[str, FilterFunc] = {
    "volume_confirm": volume_confirm,
    "candlestick_confirm": candlestick_confirm,
    "institutional_buy": institutional_buy,
}

_warned_unknown_filters: set = set()


def evaluate_filters(filters_config: List[dict], ctx: ScanContext, idx: int) -> List[str]:
    """依序評估策略設定的濾網，回傳通過的濾網 id 列表。"""
    passed = []
    for f in filters_config or []:
        f_type = f.get("type")
        func = FILTER_REGISTRY.get(f_type)
        if not func:
            if f_type not in _warned_unknown_filters:
                logger.warning(f"[策略引擎] 未知的濾網類型，已略過: {f_type}")
                _warned_unknown_filters.add(f_type)
            continue
        try:
            if func(ctx, idx, f.get("params") or {}):
                passed.append(f_type)
        except Exception as e:
            logger.warning(f"[策略引擎] 濾網 {f_type} 評估失敗 ({ctx.symbol}): {e}")
    return passed
