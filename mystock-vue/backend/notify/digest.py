"""
notify/digest.py
每日摘要彙整（§8.3、需求規格書 §M1「ALERT_DIGEST 只有此內部彙整路徑」）

tick()：每 60 秒由 main.py 的排程呼叫一次。逐一檢查候選端點是否到了它的摘要時間，
到了就把該端點所有 digest_pending / throttled 的訊息單彙整成一則 ALERT_DIGEST 訊息。

設計說明：摘要事件是「先確定收件端點，才產生內容」，與一般事件「先產生事件、再經路由展開
收件端點」的方向相反，因此不經過 routing.py（沒有目標可展開），只直接呼叫 composer 對單一
端點組裝訊息（仍然套用（ALERT_DIGEST × 管道）模板 → composer/templating 邏輯不變，只是省略
路由步驟）。

已知簡化：目前只把 ALERT_SIGNAL 來源的待彙整訊息納入摘要內容分組；其餘事件類型
（FETCH_COMPLETED 等）若因端點設為摘要模式而進入 digest_pending，仍會在此併入摘要並標記
digested（不會卡住），但不會出現在摘要內文中——多市場、多事件類型的摘要排版留待後續迭代。
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from notify import config as notify_config
from notify.events import Event, EventType, Severity

logger = logging.getLogger("mystock-backend")

_WINDOW_MIN = 5  # 摘要時間 ±5 分鐘內的 tick 都視為「到點」，NFR-05 要求 ±2 分鐘，留一點餘裕


def _endpoint_tz(endpoint: dict) -> ZoneInfo:
    try:
        return ZoneInfo(endpoint.get("timezone") or "Asia/Taipei")
    except Exception:
        return ZoneInfo("Asia/Taipei")


def _digest_time_str(endpoint: dict) -> str:
    """端點未自訂摘要時間時，退回台股預設時間（見檔案頂端「已知簡化」）"""
    v = endpoint.get("digest_send_time")
    if v is None:
        return notify_config.get_digest_time_tw()
    if isinstance(v, str):
        return v[:5]
    return f"{v.hour:02d}:{v.minute:02d}"


def _is_due(endpoint: dict) -> bool:
    tz = _endpoint_tz(endpoint)
    now_local = datetime.now(tz)
    hh, mm = (int(x) for x in _digest_time_str(endpoint).split(":")[:2])
    target = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return abs((now_local - target).total_seconds()) <= _WINDOW_MIN * 60


def _strength_label(s: str) -> str:
    return {"strong": "強", "moderate": "中", "weak": "弱"}.get(s, s)


def _build_groups(messages: list[dict]) -> dict:
    buy, sell, warn = [], [], []
    for m in messages:
        if m.get("source_event_type") != EventType.ALERT_SIGNAL:
            continue
        p = m.get("event_payload") or {}
        entry = {
            "stock_id":      p.get("stock_id", ""),
            "stock_name":    p.get("stock_name", ""),
            "strategy_name": p.get("strategy_name", ""),
            "strength_label": _strength_label(p.get("signal_strength", "")),
            "close":         (p.get("details") or {}).get("close"),
        }
        signal_type = p.get("signal_type", "")
        if signal_type == "BUY":
            buy.append(entry)
        elif signal_type == "SELL":
            sell.append(entry)
        else:
            warn.append(entry)
    # 強度排序：強 → 中 → 弱（依訂閱路由/政策模組職責分工說明，摘要以強度排序）
    order = {"強": 0, "中": 1, "弱": 2}
    for lst in (buy, sell, warn):
        lst.sort(key=lambda a: order.get(a["strength_label"], 9))
    return {"buy_list": buy, "sell_list": sell, "warning_list": warn}


async def tick(db_session: Any) -> None:
    if not notify_config.is_enabled():
        return
    try:
        from repositories.notify_repository import NotifyRepository
        from notify import composer
        from notify.policy import GateResult, GateDecision

        repo = NotifyRepository(db_session)
        endpoints = await repo.list_digest_eligible_endpoints()

        for ep in endpoints:
            if not _is_due(ep):
                continue

            pending = await repo.list_pending_digest_messages(ep["id"])
            if not pending:
                continue  # FR-PL-07：無內容不發送空白摘要

            groups = _build_groups(pending)
            total = len(groups["buy_list"]) + len(groups["sell_list"]) + len(groups["warning_list"])
            if total == 0:
                # 全部都是非 ALERT_SIGNAL 來源（見檔案頂端已知簡化）：直接標記 digested，不產生內容
                await repo.mark_messages_digested([m["id"] for m in pending], digest_message_id=None)
                continue

            digest_date = datetime.now(_endpoint_tz(ep)).strftime("%Y-%m-%d")
            payload = {
                "market":       "tw",  # 已知簡化：單一端點不分市場彙整，見檔案頂端說明
                "digest_date":  digest_date,
                "total_count":  total,
                "buy_list":     groups["buy_list"],
                "sell_list":    groups["sell_list"],
                "warning_list": groups["warning_list"],
                "endpoint_code": ep["endpoint_code"],
                "seq": 0,
            }
            event = Event(
                event_type=EventType.ALERT_DIGEST,
                severity=Severity.INFO,
                source="digest",
                occurred_at=datetime.now(timezone.utc),
                payload=payload,
                source_event_key=f"digest:{ep['endpoint_code']}:{digest_date}:0",
            )
            ikey = event.source_event_key
            event_id = await repo.upsert_event(event, ikey, {"market": "tw", "severity": "info"})

            gate = GateResult(decision=GateDecision.SEND)
            msg = await composer.compose(event, ep, gate, f"{ikey}::{ep['id']}", repo)
            if msg is None:
                continue
            msg["event_id"] = event_id
            digest_msg_id = await repo.create_message(msg)
            if not digest_msg_id:
                # ON CONFLICT DO NOTHING 命中：同一天已經彙整過一次（重複 tick），略過即可
                continue

            await repo.mark_messages_digested([m["id"] for m in pending], digest_msg_id)
            logger.info(
                "[通知] 端點 %s 摘要已產生：%d 則納入（買 %d／賣 %d／警 %d）",
                ep["endpoint_code"], len(pending),
                len(groups["buy_list"]), len(groups["sell_list"]), len(groups["warning_list"])
            )
    except Exception as exc:
        logger.warning("[通知] 摘要彙整失敗（已靜默）：%s", exc)
