"""
notify/composer.py
M4 訊息組裝（§4.6）
compose()：為路由展開的端點清單組裝訊息單（插入 notify_message 前的最後一步）
強制附加 disclaimer 和 manage_url（FR-MC-05、FR-SS-01）
鐵則 R4：composer.py 不得 import channels/
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from notify import config as notify_config
from notify.events import Event, PRIORITY_MAP
from notify.policy import GateDecision, GateResult
from notify import templating

logger = logging.getLogger("mystock-backend")

DISCLAIMER = templating.DISCLAIMER


def _chart_url(payload: dict) -> str:
    """FR-MC-04：chart_url = PUBLIC_BASE_URL + /stock/{market}/{stock_id}"""
    base     = notify_config.get_public_base_url().rstrip("/")
    market   = payload.get("market", "")
    stock_id = payload.get("stock_id", "")
    if market and stock_id:
        return f"{base}/stock/{market}/{stock_id}"
    return ""


def _manage_url(endpoint: dict, self_service_token: str | None) -> str | None:
    """
    FR-SS-01、AC-29：
    - 個人端點（personal）有自助連結
    - 共用端點（shared）或無 token → None
    """
    if not self_service_token:
        return None
    if endpoint.get("endpoint_scope") == "shared":
        return None
    base = notify_config.get_public_base_url().rstrip("/")
    return f"{base}/n/me"  # Cookie 由 /n/s/{token} 設定（§7.2）


async def compose(
    event:    Event,
    endpoint: dict,
    gate:     GateResult,
    ikey:     str,
    repo:     Any,
) -> dict | None:
    """
    組裝單一端點的訊息字典（供 repo.create_message() 使用）。
    若 gate.decision != SEND → 回傳精簡的略過記錄。
    """
    channel_code = endpoint.get("channel_code", "")
    priority     = PRIORITY_MAP.get(event.severity, 10)

    if gate.decision != GateDecision.SEND:
        # 直接記錄略過原因（不渲染模板，節省資源）
        return {
            "message_code":   f"msg-{uuid.uuid4()}",
            "event_id":       None,  # 由 intake.py 填入
            "endpoint_id":    endpoint["id"],
            "channel_code":   channel_code,
            "idempotency_key": ikey,
            "priority":       priority,
            "status":         gate.decision.value,
            "subject":        None,
            "body":           "",
            "scheduled_at":   gate.scheduled_at or datetime.now(timezone.utc),  # TIMESTAMPTZ：需原生 datetime
        }

    # ── 取得自助連結 token（個人端點）──────────────────────────
    self_token: str | None = None
    if endpoint.get("endpoint_scope") == "personal" and endpoint.get("recipient_id"):
        try:
            self_token = await repo.get_active_self_service_token(endpoint["recipient_id"])
        except Exception:
            pass

    extra_ctx = {
        "chart_url":   _chart_url(event.payload),
        "manage_url":  _manage_url(endpoint, self_token),
        "disclaimer":  DISCLAIMER,
        "occurred_at": event.occurred_at.isoformat(),
    }

    # ── 渲染模板（三層回退，§4.6 R5）──────────────────────────
    try:
        subject, body = await templating.render(
            event_type=event.event_type,
            channel_code=channel_code,
            payload=event.payload,
            extra_ctx=extra_ctx,
            repo=repo,
        )
    except Exception as exc:
        logger.error("[通知] 模板渲染例外 (ep=%s): %s", endpoint.get("endpoint_code"), exc)
        subject = None
        body    = f"[{event.event_type}] 通知（渲染失敗）\n{DISCLAIMER}"

    return {
        "message_code":   f"msg-{uuid.uuid4()}",
        "event_id":       None,  # 由 intake.py 填入
        "endpoint_id":    endpoint["id"],
        "channel_code":   channel_code,
        "idempotency_key": ikey,
        "priority":       priority,
        "status":         "pending",
        "subject":        subject,
        "body":           body,
        "scheduled_at":   gate.scheduled_at or datetime.now(timezone.utc),  # TIMESTAMPTZ：需原生 datetime
    }
