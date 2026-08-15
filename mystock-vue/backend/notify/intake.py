"""
notify/intake.py
M1 事件接收（§4.2）
publish()：接收 Event，計算冪等鍵，驅動路由→政策→組裝→寫入 Outbox
publish_alert_signals()：scanner 掃描完成後的接縫（AC-15，try/except 保護既有系統）
鐵則 R1：intake.py 不得被 strategies/ 或 services/fetcher.py import
鐵則 R7：任何通知錯誤不得讓呼叫端感知
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from notify import config as notify_config
from notify.events import Event, EventType, Severity, idempotency_key, routing_facts

logger = logging.getLogger("mystock-backend")

# 接縫保護：呼叫者的唯一接入點，失敗一律靜默（鐵則 R7）
_SEAM_ENABLED = True  # 可由測試 mock 改為 False


async def publish(event: Event, db_session: Any) -> dict:
    """
    接收 Event，執行完整路由→政策→組裝→寫入 Outbox 流程（§4.2）。
    回傳 {"event_id": int, "messages_created": int, "messages_skipped": int}
    不拋例外（鐵則 R7）。
    """
    if not notify_config.is_enabled():
        return {"event_id": None, "messages_created": 0, "messages_skipped": 0}

    try:
        from repositories.notify_repository import NotifyRepository
        from notify import routing, policy, composer

        repo = NotifyRepository(db_session)

        # 1. 計算冪等鍵，落地事件
        ikey      = idempotency_key(event)
        facts     = routing_facts(event)
        event_id  = await repo.upsert_event(event, ikey, facts)

        # 2. M2 路由：展開端點清單
        endpoints = await routing.resolve_endpoints(event.event_type, facts, repo)
        if not endpoints:
            await repo.mark_event_routed(event_id, "no_match")
            return {"event_id": event_id, "messages_created": 0, "messages_skipped": 0}

        # 3. M3 政策 + M4 組裝 + 寫入 Outbox（每端點一次）
        created = skipped = 0
        for ep in endpoints:
            ep_ikey = f"{ikey}::{ep['id']}"  # 端點維度的冪等鍵
            try:
                gate = await policy.apply_gates(event, ep, ep_ikey, repo)
                msg  = await composer.compose(event, ep, gate, ep_ikey, repo)
                if msg is None:
                    continue
                msg["event_id"] = event_id
                await repo.create_message(msg)
                if msg.get("status") == "pending":
                    created += 1
                else:
                    skipped += 1
            except Exception as ep_exc:
                logger.warning("[通知] 端點 %s 訊息建立失敗：%s", ep.get("endpoint_code"), ep_exc)
                skipped += 1

        await repo.mark_event_routed(event_id, "routed")
        logger.info(
            "[通知] 事件已接收：event_id=%s type=%s created=%d skipped=%d",
            event_id, event.event_type, created, skipped
        )
        return {"event_id": event_id, "messages_created": created, "messages_skipped": skipped}

    except Exception as exc:
        # 鐵則 R7：通知系統任何錯誤不影響呼叫端
        logger.warning("[通知] publish() 失敗（已靜默）：%s", exc)
        return {"event_id": None, "messages_created": 0, "messages_skipped": 0}


async def publish_alert_signals(
    market:       str,
    trade_date:   str,
    alerts:       list[dict],
    db_session:   Any,
) -> None:
    """
    接縫：掃描器完成後由 scheduler._publish_after_scan() 呼叫。
    AC-15：此函數整個包在 try/except，掃描完成不會因通知失敗而受影響。
    """
    if not _SEAM_ENABLED or not notify_config.is_enabled():
        return
    if not alerts:
        return

    # 每筆警示訊號轉為 ALERT_SIGNAL 事件
    occurred_at = datetime.now(timezone.utc)
    for alert in alerts:
        try:
            payload = {
                "stock_id":       alert.get("stock_id", ""),
                "stock_name":     alert.get("stock_name", ""),
                "market":         market,
                "strategy_id":    alert.get("strategy_id", ""),
                "strategy_name":  alert.get("strategy_name", ""),
                "direction":      alert.get("direction", ""),
                "signal_type":    alert.get("signal_type", ""),
                "signal_strength": alert.get("signal_strength", "moderate"),
                "trade_date":     trade_date,
                "details":        alert.get("details", {}),
                "filters_passed": alert.get("filters_passed", []),
                "suggested_action": alert.get("suggested_action", ""),
            }
            ev = Event(
                event_type=EventType.ALERT_SIGNAL,
                severity=Severity.INFO,
                source="scanner",
                occurred_at=occurred_at,
                payload=payload,
                source_event_key=alert.get("id"),
            )
            await publish(ev, db_session)
        except Exception as exc:
            logger.warning("[通知] publish_alert_signals 單筆失敗（已靜默）：%s", exc)


async def publish_fetch_completed(
    market:      str,
    trade_date:  str,
    summary:     dict,
    db_session:  Any,
) -> None:
    """抓取完成事件（掃描器在 fetch 完成後呼叫）"""
    if not notify_config.is_enabled():
        return
    try:
        ev = Event(
            event_type=EventType.FETCH_COMPLETED,
            severity=Severity.INFO,
            source="fetcher",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "market":      market,
                "trade_date":  trade_date,
                **summary,
            },
        )
        await publish(ev, db_session)
    except Exception as exc:
        logger.warning("[通知] publish_fetch_completed 失敗（已靜默）：%s", exc)


async def publish_fetch_failed(
    market:        str,
    trade_date:    str,
    error_summary: str,
    failed_symbols: list[str],
    db_session:    Any,
) -> None:
    """抓取失敗事件（severity=critical，跳過閘門 2/3/4）"""
    if not notify_config.is_enabled():
        return
    try:
        ev = Event(
            event_type=EventType.FETCH_FAILED,
            severity=Severity.CRITICAL,
            source="fetcher",
            occurred_at=datetime.now(timezone.utc),
            payload={
                "market":         market,
                "trade_date":     trade_date,
                "error_summary":  error_summary,
                "failed_symbols": failed_symbols,
            },
        )
        await publish(ev, db_session)
    except Exception as exc:
        logger.warning("[通知] publish_fetch_failed 失敗（已靜默）：%s", exc)
