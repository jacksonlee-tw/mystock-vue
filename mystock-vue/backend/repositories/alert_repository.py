"""ALERT_EVENT / SIGNAL_COOLDOWN 的唯一資料存取入口（策略管理架構 設計文件第 3 節）。

目前用 JSON 檔儲存（呼應均線策略警示系統 設計文件開放問題 Q-1：DATA_SOURCE=json 時先用 JSON，
欄位命名對齊 doc1 的 ALERT_EVENT/SIGNAL_COOLDOWN schema，之後要遷 Postgres 時容易對應）。
掃描器（strategies/scanner.py）與 API 層都只透過這裡讀寫，不直接碰檔案路徑。
"""
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import DATA_DIR

ALERTS_DIR = os.path.join(DATA_DIR, "_alerts")
ALERTS_FILE = os.path.join(ALERTS_DIR, "alerts.json")
COOLDOWN_FILE = os.path.join(ALERTS_DIR, "cooldown.json")


def _ensure_dir() -> None:
    os.makedirs(ALERTS_DIR, exist_ok=True)


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: str, data: Any) -> None:
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── alerts.json ──────────────────────────────────────────────────────────
def _load_alerts() -> List[Dict[str, Any]]:
    return _load_json(ALERTS_FILE, [])


def load_existing_signal_keys() -> set:
    """回傳目前已存在的 (symbol, strategy_id, direction, trade_date) 組合，
    供掃描器判斷同一天重複執行時是否要略過（見策略管理架構 設計文件第 2 節「防過度觸發與去重」）。"""
    alerts = _load_alerts()
    return {(a["stock_id"], a["strategy_id"], a["direction"], a["trade_date"]) for a in alerts}


def append_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """幫每筆新警示補上 id/timestamp 並寫入。alerts 需已含 stock_id/strategy_id/trade_date 等欄位
    （見均線策略警示系統 設計文件第 6.2 節契約），回傳補好 id/timestamp 後的完整清單。"""
    if not alerts:
        return []

    existing = _load_alerts()
    seq_counter: Dict[str, int] = {}
    for a in existing:
        prefix = f"{a['trade_date'].replace('-', '')}-{a['stock_id']}"
        seq_counter[prefix] = max(seq_counter.get(prefix, 0), int(a["id"].rsplit("-", 1)[-1]))

    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    finalized = []
    for a in alerts:
        prefix = f"{a['trade_date'].replace('-', '')}-{a['stock_id']}"
        seq = seq_counter.get(prefix, 0) + 1
        seq_counter[prefix] = seq
        record = {**a, "id": f"alert-{prefix}-{seq:03d}", "timestamp": now_iso}
        finalized.append(record)

    _save_json(ALERTS_FILE, existing + finalized)
    return finalized


def query_alerts(
    market: Optional[str] = None,
    days: int = 7,
    strategy_id: Optional[str] = None,
    symbol: Optional[str] = None,
    strength: Optional[str] = None,
) -> List[Dict[str, Any]]:
    alerts = _load_alerts()

    if market:
        alerts = [a for a in alerts if a.get("market") == market]
    if strategy_id:
        alerts = [a for a in alerts if a.get("strategy_id") == strategy_id]
    if symbol:
        alerts = [a for a in alerts if a.get("stock_id") == symbol]
    if strength:
        alerts = [a for a in alerts if a.get("signal_strength") == strength]
    if days is not None:
        cutoff = (datetime.now().date() - timedelta(days=days)).isoformat()
        alerts = [a for a in alerts if a.get("trade_date", "") >= cutoff]

    return sorted(alerts, key=lambda a: (a.get("trade_date", ""), a.get("timestamp", "")), reverse=True)


# ── cooldown.json ────────────────────────────────────────────────────────
def load_cooldown_state() -> Dict[str, str]:
    return _load_json(COOLDOWN_FILE, {})


def save_cooldown_state(state: Dict[str, str]) -> None:
    _save_json(COOLDOWN_FILE, state)
