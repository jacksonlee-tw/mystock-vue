"""持倉出場與風控條件函式實作（選股功能與爬蟲 規格書 §6、§13）。

包含：
1. `trailing_stop`：移動停利（自進場後最高價回檔超過指定百分比）
2. `fixed_stop_loss`：固定停損（跌破平均成本達指定百分比）
3. `time_stop`：時間停損（持股超過上限天數且報酬未達預期）
"""
from typing import Any, Dict, List, Optional

from services.chip_provider import ScanContext
from strategies.registry import condition


@condition(type="trailing_stop", min_bars=1, requires=("raw_records",))
def trailing_stop(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """移動停利條件：當前收盤價自進場後最高收盤價回檔超過 drawdown_pct。"""
    drawdown_pct = params.get("drawdown_pct", 10.0)
    current_close = ctx.closes[idx]
    if current_close is None:
        return []

    # 1. 優先使用 PositionContext
    if ctx.position and ctx.position.peak_close_since_entry > 0:
        peak = max(ctx.position.peak_close_since_entry, current_close)
        dd = (current_close - peak) / peak * 100.0
        if dd <= -drawdown_pct:
            return [{
                "direction": "exit_trailing_stop",
                "details": {
                    "peak_close": peak,
                    "current_close": current_close,
                    "drawdown_pct": round(dd, 2),
                    "threshold_pct": -drawdown_pct,
                },
            }]
        return []

    # 2. 無持倉資訊時，以近 rolling_window 天最高價計算
    window = params.get("rolling_window", 20)
    start = max(0, idx - window + 1)
    valid_closes = [c for c in ctx.closes[start : idx + 1] if c is not None]
    if not valid_closes:
        return []
    peak = max(valid_closes)
    dd = (current_close - peak) / peak * 100.0
    if dd <= -drawdown_pct:
        return [{
            "direction": "exit_trailing_stop",
            "details": {
                "peak_close": peak,
                "current_close": current_close,
                "drawdown_pct": round(dd, 2),
                "threshold_pct": -drawdown_pct,
            },
        }]
    return []


@condition(type="fixed_stop_loss", min_bars=1, requires=("raw_records",))
def fixed_stop_loss(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """固定停損條件：當前收盤價較平均成本虧損達 stop_loss_pct。"""
    stop_loss_pct = params.get("stop_loss_pct", 8.0)
    current_close = ctx.closes[idx]
    if current_close is None:
        return []

    if ctx.position and ctx.position.avg_cost > 0:
        loss_pct = (current_close - ctx.position.avg_cost) / ctx.position.avg_cost * 100.0
        if loss_pct <= -stop_loss_pct:
            return [{
                "direction": "exit_stop_loss",
                "details": {
                    "avg_cost": ctx.position.avg_cost,
                    "current_close": current_close,
                    "loss_pct": round(loss_pct, 2),
                    "threshold_pct": -stop_loss_pct,
                },
            }]

    return []


@condition(type="time_stop", min_bars=1, requires=("raw_records",))
def time_stop(ctx: ScanContext, idx: int, params: dict) -> List[dict]:
    """時間停損條件：持股已達 max_holding_days 交易日，且未實現報酬低於 min_return_pct。"""
    max_days = params.get("max_holding_days", 60)
    min_return = params.get("min_return_pct", 0.0)

    if not ctx.position:
        return []

    if ctx.position.holding_trading_days >= max_days:
        if ctx.position.unrealized_return_pct < min_return:
            return [{
                "direction": "exit_time_stop",
                "details": {
                    "holding_trading_days": ctx.position.holding_trading_days,
                    "max_holding_days": max_days,
                    "unrealized_return_pct": ctx.position.unrealized_return_pct,
                    "min_return_pct": min_return,
                },
            }]

    return []
