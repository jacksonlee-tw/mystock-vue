"""
notify/events.py
事件契約：Event dataclass、EventType、Severity、冪等鍵計算、routing facts 擷取（§4.1）
"""
from __future__ import annotations
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger("mystock-backend")


class EventType(str, Enum):
    ALERT_SIGNAL    = "ALERT_SIGNAL"
    ALERT_DIGEST    = "ALERT_DIGEST"
    FETCH_COMPLETED = "FETCH_COMPLETED"
    FETCH_FAILED    = "FETCH_FAILED"
    SYSTEM_HEALTH   = "SYSTEM_HEALTH"


class Severity(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


# 優先度對照（priority ASC → critical 先送）
PRIORITY_MAP: dict[str, int] = {
    Severity.CRITICAL: 0,
    Severity.WARNING:  5,
    Severity.INFO:     10,
}


@dataclass(frozen=True)
class Event:
    event_type:      str           # EventType 之一
    severity:        str           # Severity 之一
    source:          str           # scanner / fetcher / health_probe / manual
    occurred_at:     datetime      # tz-aware
    payload:         dict
    source_event_key: str | None = None  # 來源已有的穩定識別鍵


# ── 冪等鍵建構器（ADR-11，跨重跑穩定）────────────────────────────
def _key_alert_signal(payload: dict) -> str:
    market      = payload.get("market", "")
    stock_id    = payload.get("stock_id", "")
    strategy_id = payload.get("strategy_id", "")
    direction   = payload.get("direction", "")
    trade_date  = payload.get("trade_date", "")
    return f"alert:{market}:{stock_id}:{strategy_id}:{direction}:{trade_date}"


def _key_alert_digest(payload: dict) -> str:
    endpoint_code = payload.get("endpoint_code", "")
    digest_date   = payload.get("digest_date", "")
    seq           = payload.get("seq", 0)
    return f"digest:{endpoint_code}:{digest_date}:{seq}"


def _key_fetch_completed(payload: dict) -> str:
    market       = payload.get("market", "")
    trade_date   = payload.get("trade_date", "")
    trigger_type = payload.get("trigger_type", "scheduled")
    return f"fetch_ok:{market}:{trade_date}:{trigger_type}"


def _key_fetch_failed(payload: dict) -> str:
    market     = payload.get("market", "")
    trade_date = payload.get("trade_date", "")
    digest     = hashlib.md5(str(payload.get("error_summary", "")).encode()).hexdigest()[:8]
    return f"fetch_fail:{market}:{trade_date}:{digest}"


def _key_system_health(payload: dict) -> str:
    probe_key       = payload.get("probe_key", "unknown")
    cooldown_bucket = payload.get("cooldown_bucket", "default")
    return f"health:{probe_key}:{cooldown_bucket}"


KEY_BUILDERS: dict[str, callable] = {
    EventType.ALERT_SIGNAL:    _key_alert_signal,
    EventType.ALERT_DIGEST:    _key_alert_digest,
    EventType.FETCH_COMPLETED: _key_fetch_completed,
    EventType.FETCH_FAILED:    _key_fetch_failed,
    EventType.SYSTEM_HEALTH:   _key_system_health,
}


def idempotency_key(event: Event) -> str:
    """
    計算冪等鍵：來源鍵優先；無來源鍵時依事件類型的業務欄位組合（ADR-11）
    """
    if event.source_event_key:
        return event.source_event_key
    builder = KEY_BUILDERS.get(event.event_type)
    if builder is None:
        # 未知類型：以 event_type + occurred_at 的 hash 作為後備
        raw = f"{event.event_type}:{event.occurred_at.isoformat()}:{str(event.payload)}"
        return "unknown:" + hashlib.sha256(raw.encode()).hexdigest()[:32]
    return builder(event.payload)


# ── Routing facts 擷取（§4.4，攤平為可比對的鍵值）────────────────
def _facts_alert_signal(payload: dict) -> dict:
    """從 payload 擷取 ALERT_SIGNAL 路由事實"""
    # strategy_category 從 strategies.yaml 反查（避免改動 R1 邊界）
    strategy_category = _get_strategy_category(payload.get("strategy_id", ""))
    return {
        "market":            payload.get("market", ""),
        "strategy_id":       payload.get("strategy_id", ""),
        "strategy_category": strategy_category,
        "signal_type":       payload.get("signal_type", ""),
        "signal_strength":   payload.get("signal_strength", ""),
        "stock_id":          payload.get("stock_id", ""),
    }


def _facts_generic(payload: dict) -> dict:
    return {}


ROUTING_FACTS: dict[str, callable] = {
    EventType.ALERT_SIGNAL:    _facts_alert_signal,
    EventType.ALERT_DIGEST:    _facts_generic,
    EventType.FETCH_COMPLETED: _facts_generic,
    EventType.FETCH_FAILED:    _facts_generic,
    EventType.SYSTEM_HEALTH:   _facts_generic,
}


def routing_facts(event: Event) -> dict:
    extractor = ROUTING_FACTS.get(event.event_type, _facts_generic)
    facts = extractor(event.payload)
    facts["severity"] = event.severity
    return facts


def _get_strategy_category(strategy_id: str) -> str:
    """從 strategies.yaml 反查 strategy_id 的 category（§4.4）"""
    if not strategy_id:
        return "unknown"
    try:
        from strategies.config_loader import load_strategy_config
        cfg = load_strategy_config().get(strategy_id)
        if cfg and cfg.category:
            return cfg.category
    except Exception:
        pass
    return "unknown"


# ── 模板渲染上下文規格（供管理介面「變數說明」讀取）──────────────
TEMPLATE_CONTEXT_SPEC: dict[str, list[dict]] = {
    EventType.ALERT_SIGNAL: [
        {"var": "stock_id",        "desc": "股票代號",       "example": "2330"},
        {"var": "stock_name",      "desc": "股票名稱",       "example": "台積電"},
        {"var": "market",          "desc": "市場",           "example": "tw"},
        {"var": "strategy_name",   "desc": "策略名稱",       "example": "收盤價突破關鍵均線"},
        {"var": "signal_type",     "desc": "訊號類型",       "example": "SELL"},
        {"var": "signal_strength", "desc": "訊號強度",       "example": "moderate"},
        {"var": "trade_date",      "desc": "交易日",         "example": "2026-08-14"},
        {"var": "details",         "desc": "技術數值（dict）","example": '{"close":1085,"ma_period":20}'},
        {"var": "suggested_action","desc": "建議動作",       "example": "跌破 MA20"},
        {"var": "chart_url",       "desc": "圖表連結",       "example": "https://..."},
        {"var": "manage_url",      "desc": "管理連結（個人端點才有值）", "example": "https://..."},
        {"var": "disclaimer",      "desc": "免責聲明（自動附加）",   "example": "本訊息為系統依既定規則產生的資訊提示，非投資建議。"},
        {"var": "emoji",           "desc": "訊號 emoji",    "example": "📉"},
        {"var": "signal_label",    "desc": "訊號標籤",       "example": "賣出訊號"},
        {"var": "strength_label",  "desc": "強度標籤",       "example": "中"},
        {"var": "filters_passed",  "desc": "通過濾網清單",   "example": '["volume_confirm"]'},
    ],
    EventType.FETCH_COMPLETED: [
        {"var": "market",         "desc": "市場",   "example": "tw"},
        {"var": "trade_date",     "desc": "交易日", "example": "2026-08-14"},
        {"var": "success_count",  "desc": "成功筆數","example": "50"},
        {"var": "failure_count",  "desc": "失敗筆數","example": "0"},
        {"var": "elapsed_sec",    "desc": "耗時（秒）","example": "12.3"},
        {"var": "disclaimer",     "desc": "免責聲明", "example": ""},
    ],
    EventType.FETCH_FAILED: [
        {"var": "market",         "desc": "市場",     "example": "tw"},
        {"var": "trade_date",     "desc": "交易日",   "example": "2026-08-14"},
        {"var": "error_summary",  "desc": "錯誤摘要", "example": "連線逾時"},
        {"var": "failed_symbols", "desc": "失敗標的清單", "example": '["2330","0050"]'},
        {"var": "disclaimer",     "desc": "免責聲明", "example": ""},
    ],
    EventType.SYSTEM_HEALTH: [
        {"var": "probe_key",    "desc": "偵測項目鍵", "example": "tw_data_missing"},
        {"var": "description",  "desc": "異常說明",   "example": "台股今日資料未寫入"},
        {"var": "occurred_at",  "desc": "發生時間",   "example": "2026-08-14 15:30"},
        {"var": "disclaimer",   "desc": "免責聲明",   "example": ""},
    ],
    EventType.ALERT_DIGEST: [
        {"var": "market",        "desc": "市場",          "example": "tw"},
        {"var": "digest_date",   "desc": "摘要日期",       "example": "2026-08-14"},
        {"var": "total_count",   "desc": "訊號總數",       "example": "5"},
        {"var": "buy_list",      "desc": "買進訊號列表",   "example": '[]'},
        {"var": "sell_list",     "desc": "賣出訊號列表",   "example": '[]'},
        {"var": "warning_list",  "desc": "警告訊號列表",   "example": '[]'},
        {"var": "manage_url",    "desc": "管理連結",       "example": ""},
        {"var": "disclaimer",    "desc": "免責聲明",       "example": ""},
    ],
}

# 範例 payload（供 POST /templates/preview）
SAMPLE_PAYLOADS: dict[str, dict] = {
    EventType.ALERT_SIGNAL: {
        "stock_id": "2330", "stock_name": "台積電", "market": "tw",
        "strategy_id": "price_cross_ma", "strategy_name": "收盤價突破關鍵均線",
        "direction": "cross_under_MA20", "signal_type": "SELL", "signal_strength": "moderate",
        "trade_date": "2026-08-14",
        "details": {"close": 1085, "ma_period": 20, "ma_value": 1102.5, "bias_percent": -1.59},
        "filters_passed": ["volume_confirm"], "suggested_action": "跌破 MA20，建議減碼"
    },
    EventType.FETCH_COMPLETED: {
        "market": "tw", "trade_date": "2026-08-14", "success_count": 50, "failure_count": 0, "elapsed_sec": 12.3
    },
    EventType.FETCH_FAILED: {
        "market": "tw", "trade_date": "2026-08-14", "error_summary": "連線逾時", "failed_symbols": ["2330"]
    },
    EventType.SYSTEM_HEALTH: {
        "probe_key": "tw_data_missing", "description": "台股今日資料未寫入", "cooldown_bucket": "default"
    },
    EventType.ALERT_DIGEST: {
        "market": "tw", "digest_date": "2026-08-14", "total_count": 3,
        "buy_list": [{"stock_id": "0050", "strategy_name": "均線", "strength": "strong"}],
        "sell_list": [{"stock_id": "2330", "strategy_name": "均線", "strength": "moderate"}],
        "warning_list": []
    },
}
