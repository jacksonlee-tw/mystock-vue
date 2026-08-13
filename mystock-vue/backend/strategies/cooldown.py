"""訊號去重（Cooldown）機制（策略管理架構 設計文件第 3 節 SIGNAL_COOLDOWN）。

純邏輯，不碰任何檔案 I/O ── 狀態的讀寫交給 repositories/alert_repository.py，
維持策略引擎跟儲存方式解耦（同一原則見 services/chip_provider.py）。
"""
from datetime import date
from typing import Dict


def cooldown_key(symbol: str, strategy_id: str, direction: str) -> str:
    return f"{symbol}|{strategy_id}|{direction}"


def is_active(state: Dict[str, str], key: str, today: str, cooldown_days: int) -> bool:
    """last_triggered_at 到 today 的天數若小於 cooldown_days，視為仍在冷卻期內。"""
    last = state.get(key)
    if not last:
        return False
    try:
        return (date.fromisoformat(today) - date.fromisoformat(last)).days < cooldown_days
    except ValueError:
        return False


def mark(state: Dict[str, str], key: str, today: str) -> None:
    state[key] = today
