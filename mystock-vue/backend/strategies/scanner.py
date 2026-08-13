"""策略掃描主邏輯（策略管理架構 設計文件「核心業務流程：策略掃描與警示觸發」）。

流程：讀取 YAML 設定 → 逐標的透過 ChipDataProvider 取資料 → 逐策略逐條件掃描 →
通過濾網算強度 → 去重（同日重複執行 / Cooldown）→ 寫入警示記錄。
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import repositories.alert_repository as alert_repository
from config import get_alert_cooldown_days, get_target_stocks
from services.chip_provider import ChipDataProvider
from strategies import cooldown as cooldown_mod
from strategies.config_loader import load_strategy_config
from strategies.direction import classify_direction, to_signal_type
from strategies.filters import evaluate_filters
from strategies.registry import CONDITION_REGISTRY

logger = logging.getLogger("mystock-backend")

_SUGGESTED_ACTION_TEMPLATES = {
    ("price_cross_ma", "bullish"): "可納入多頭觀察清單，停損參考 MA{ma_period} 下 3%（{stop_loss}）",
    ("price_cross_ma", "bearish"): "跌破 MA{ma_period}，建議減碼或設定停損觀察",
    ("ma_golden_death_cross", "bullish"): "均線黃金交叉，趨勢轉強訊號，可留意進場時機",
    ("ma_golden_death_cross", "bearish"): "均線死亡交叉，趨勢轉弱，建議降低持股比重",
    ("ma_alignment", "bullish"): "均線多頭排列成形，動能轉強，可列入強勢股觀察",
    ("ma_alignment", "bearish"): "均線空頭排列成形，趨勢偏弱，不宜逢低攤平",
    ("ma_squeeze_breakout", "bullish"): "均線糾結後帶量突破，留意起漲點",
    ("extreme_bias", "bearish"): "正乖離過大，短線過熱，留意獲利了結賣壓",
    ("extreme_bias", "bullish"): "負乖離過大，超跌可能醞釀反彈，留意止跌訊號",
    ("ma_pullback_support", "bullish"): "回踩均線支撐未破，為趨勢股拉回找買點的參考時機",
}


def _strength(passed_filter_count: int) -> str:
    """訊號強度分級（均線策略警示系統 設計文件第 8.3 節）。"""
    if passed_filter_count >= 2:
        return "strong"
    if passed_filter_count == 1:
        return "moderate"
    return "weak"


def _suggested_action(strategy_id: str, direction: str, details: dict) -> str:
    template = _SUGGESTED_ACTION_TEMPLATES.get((strategy_id, classify_direction(direction)))
    if not template:
        return ""
    ma_period = details.get("ma_period")
    ma_value = details.get("ma_value")
    stop_loss = round(ma_value * 0.97, 2) if ma_value else "-"
    return template.format(ma_period=ma_period, stop_loss=stop_loss)


async def scan_market(
    market: str,
    lookback_days: Optional[int] = None,
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    started = time.perf_counter()
    cfg = load_strategy_config()
    lookback = lookback_days or cfg.defaults.get("lookback_days", 1)
    ma_periods = cfg.defaults.get("ma_periods", [5, 10, 20, 60, 120, 240])
    volume_ma_period = cfg.defaults.get("volume_ma_period", 5)
    cooldown_days = get_alert_cooldown_days()

    target_symbols = symbols or get_target_stocks(market=market)
    strategies = cfg.enabled_for_market(market)
    provider = ChipDataProvider()

    existing_keys = alert_repository.load_existing_signal_keys()
    cooldown_state = alert_repository.load_cooldown_state()
    new_alerts: List[Dict[str, Any]] = []

    for symbol in target_symbols:
        try:
            ctx = await provider.get_bars(symbol, market, ma_periods, volume_ma_period)
        except Exception as e:
            logger.warning(f"[策略引擎] 取得 {symbol} 資料失敗，已略過: {e}")
            continue
        if ctx is None:
            continue

        start_idx = max(0, ctx.length - lookback)

        for strategy in strategies:
            for condition_cfg in strategy.conditions:
                spec = CONDITION_REGISTRY.get(condition_cfg.get("type"))
                if not spec:
                    logger.warning(f"[策略引擎] 未知的條件類型，已略過: {condition_cfg.get('type')}")
                    continue

                for idx in range(start_idx, ctx.length):
                    try:
                        signals = spec.func(ctx, idx, condition_cfg)
                    except Exception as e:
                        logger.warning(f"[策略引擎] 條件 {spec.type} 評估失敗 ({symbol}): {e}")
                        continue
                    if not signals:
                        continue

                    trade_date = ctx.dates[idx]
                    for signal in signals:
                        direction = signal["direction"]
                        dedup_key = (symbol, strategy.id, direction, trade_date)
                        if dedup_key in existing_keys:
                            continue

                        cd_key = cooldown_mod.cooldown_key(symbol, strategy.id, direction)
                        if cooldown_mod.is_active(cooldown_state, cd_key, trade_date, cooldown_days):
                            continue

                        passed_filters = evaluate_filters(strategy.filters, ctx, idx)
                        details = signal.get("details", {})

                        new_alerts.append({
                            "stock_id": symbol,
                            "stock_name": ctx.name,
                            "market": market,
                            "strategy_id": strategy.id,
                            "strategy_name": strategy.name,
                            "direction": direction,
                            "signal_type": to_signal_type(direction),
                            "signal_strength": _strength(len(passed_filters)),
                            "trade_date": trade_date,
                            "details": details,
                            "filters_passed": passed_filters,
                            "suggested_action": _suggested_action(strategy.id, direction, details),
                        })
                        existing_keys.add(dedup_key)
                        cooldown_mod.mark(cooldown_state, cd_key, trade_date)

    finalized = alert_repository.append_alerts(new_alerts)
    if new_alerts:
        alert_repository.save_cooldown_state(cooldown_state)

    return {
        "scanned_stocks": len(target_symbols),
        "alerts_generated": len(finalized),
        "scan_duration_ms": int((time.perf_counter() - started) * 1000),
    }


def scan_market_sync(
    market: str,
    lookback_days: Optional[int] = None,
    symbols: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """供同步呼叫端（排程 callback）使用，比照 repositories/stock_repository.py 的 run_async() 作法：
    獨立開一個新的事件迴圈執行，呼叫端所在的執行緒不可已經身處事件迴圈中。"""
    return asyncio.run(scan_market(market, lookback_days=lookback_days, symbols=symbols))
