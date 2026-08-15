"""
notify/recipients.py
M8 收件人管理（§6.3 M8）
- 收件人／端點／群組的建立與維護
- FR-RC-04：新增收件端點是純資料操作，不需修改設定檔或重啟系統
- FR-RC-09：個人端點必須有 recipient_id；共用端點必須沒有（DB CHECK 已強制，這裡再擋一次給前端更好的錯誤訊息）
"""
from __future__ import annotations
import logging
import uuid
from typing import Any

from notify import config as notify_config
from notify.security import NotifyValidationException, NotifyNotFoundException
from notify.templating import DISCLAIMER
from notify.timeutil import parse_time

logger = logging.getLogger("mystock-backend")


def _new_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ── 收件人 ────────────────────────────────────────────────────
async def create_recipient(display_name: str, group_codes: list[str] | None, repo: Any) -> dict:
    if not display_name or not display_name.strip():
        raise NotifyValidationException("顯示名稱不可為空")

    recipient_id = await repo.create_recipient({
        "recipient_code": _new_code("rcp"),
        "display_name":   display_name.strip(),
        "status":         "active",
    })
    # 建立預設偏好：ceiling_* 是系統擁有者指派的授權上限（此處先給全範圍，
    # 管理介面可再收緊）；allowed_* 是收件人目前的有效選擇，依 Q-03 決策預設
    # 「強＋中即時、弱僅摘要」，初始與 ceiling 相同即代表尚未自行收窄（FR-SS-08、V4 migration）。
    full_scope = {
        "markets":             ["tw", "us"],
        "strengths":           ["strong", "moderate", "weak"],
        "signal_types":        ["BUY", "SELL", "WARNING"],
        "strategy_categories": ["technical", "chip", "fundamental"],
    }
    await repo.upsert_preference(recipient_id, {
        "ceiling_markets":             full_scope["markets"],
        "ceiling_strengths":           full_scope["strengths"],
        "ceiling_signal_types":        full_scope["signal_types"],
        "ceiling_strategy_categories": full_scope["strategy_categories"],
        "allowed_markets":             full_scope["markets"],
        "allowed_strengths":           full_scope["strengths"],
        "allowed_signal_types":        full_scope["signal_types"],
        "allowed_strategy_categories": full_scope["strategy_categories"],
        "watch_symbols":               None,
    })

    for gcode in (group_codes or []):
        group = await repo.get_group_by_code(gcode)
        if group:
            await repo.add_group_member(group["id"], recipient_id)

    logger.info("[通知] 新增收件人 id=%s name=%s", recipient_id, display_name)
    return await repo.get_recipient(recipient_id)


async def update_recipient(recipient_id: int, updates: dict, repo: Any) -> None:
    allowed = {k: v for k, v in updates.items() if k in ("display_name", "status")}
    if not allowed:
        return
    await repo.update_recipient(recipient_id, allowed)


async def disable_recipient(recipient_id: int, repo: Any) -> None:
    """FR-RC-08：停用保留歷史，不刪除任何紀錄"""
    await repo.update_recipient(recipient_id, {"status": "disabled"})
    for ep in await repo.list_endpoints_for_recipient(recipient_id):
        await repo.update_endpoint(ep["id"], {"status": "disabled"})


# ── 端點 ──────────────────────────────────────────────────────
async def create_personal_endpoint(
    recipient_code: str,
    channel_code:   str,
    address:        str,
    repo:           Any,
    **prefs,
) -> dict:
    """
    新增個人端點（Email／Telegram 皆走此函式）。
    Email：立即建立並回傳 endpoint，由呼叫端（API 層）接著呼叫 binding.issue_email_verification()。
    Telegram：先建立 endpoint（verify_status=pending），由呼叫端接著呼叫 binding.issue_binding_code()。
    """
    recipient = await repo.get_recipient_by_code(recipient_code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{recipient_code}")

    from notify.channel_config import validate_channel_settings
    from notify.channels import get_channel
    adapter = get_channel(channel_code)
    if adapter is None:
        raise NotifyValidationException(f"未知管道代碼：{channel_code}")

    normalized = adapter.normalize_address(address)
    existing = await repo.get_endpoint_by_address(channel_code, normalized)
    if existing:
        raise NotifyValidationException("同一管道下不可重複建立相同收件位址")

    endpoint_id = await repo.create_endpoint({
        "endpoint_code":        _new_code("ep"),
        "channel_code":         channel_code,
        "recipient_id":         recipient["id"],
        "endpoint_scope":       "personal",
        "address":              normalized,
        "verify_status":        "pending",
        "status":               "active",
        "delivery_mode":        prefs.get("delivery_mode", "digest" if channel_code == "email" else "realtime"),
        # TIME 欄位：asyncpg 需要原生 datetime.time，不接受 'HH:MM' 字串（notify/timeutil.py）
        "quiet_start":          parse_time(prefs.get("quiet_start", notify_config.get_default_quiet_start())),
        "quiet_end":            parse_time(prefs.get("quiet_end", notify_config.get_default_quiet_end())),
        "timezone":             prefs.get("timezone", notify_config.get_default_timezone()),
        "daily_limit":          prefs.get("daily_limit", notify_config.get_default_daily_limit()),
        "digest_send_time":     parse_time(prefs.get("digest_send_time")),
        "fallback_endpoint_id": prefs.get("fallback_endpoint_id"),
    })
    logger.info("[通知] 新增個人端點 id=%s channel=%s recipient=%s", endpoint_id, channel_code, recipient_code)
    return await repo.get_endpoint(endpoint_id)


async def create_shared_endpoint(channel_code: str, address: str, display_note: str, repo: Any) -> dict:
    """
    新增共用端點（如 Telegram 群組）：不屬於任何收件人，不產生自助連結（FR-RC-09、RK-10）。
    """
    from notify.channels import get_channel
    adapter = get_channel(channel_code)
    if adapter is None:
        raise NotifyValidationException(f"未知管道代碼：{channel_code}")

    normalized = adapter.normalize_address(address)
    existing = await repo.get_endpoint_by_address(channel_code, normalized)
    if existing:
        raise NotifyValidationException("同一管道下不可重複建立相同收件位址")

    endpoint_id = await repo.create_endpoint({
        "endpoint_code":        _new_code("ep"),
        "channel_code":         channel_code,
        "recipient_id":         None,
        "endpoint_scope":       "shared",
        "address":              normalized,
        "verify_status":        "verified",  # 共用端點由擁有者手動建立，視同已驗證
        "status":               "active",
        "delivery_mode":        "critical_only",
        "quiet_start":          parse_time(notify_config.get_default_quiet_start()),
        "quiet_end":            parse_time(notify_config.get_default_quiet_end()),
        "timezone":             notify_config.get_default_timezone(),
        "daily_limit":          notify_config.get_default_daily_limit(),
        "digest_send_time":     None,
        "fallback_endpoint_id": None,
    })
    logger.info("[通知] 新增共用端點 id=%s channel=%s note=%s", endpoint_id, channel_code, display_note)
    return await repo.get_endpoint(endpoint_id)


async def set_endpoint_preferences(endpoint_code: str, updates: dict, repo: Any) -> dict:
    """FR-RC-06：每個端點可獨立設定發送模式、靜音時段、頻率上限"""
    ep = await repo.get_endpoint_by_code(endpoint_code)
    if not ep:
        raise NotifyNotFoundException(f"端點不存在：{endpoint_code}")

    allowed_keys = {
        "delivery_mode", "quiet_start", "quiet_end", "timezone",
        "daily_limit", "digest_send_time", "fallback_endpoint_id",
    }
    payload = {k: v for k, v in updates.items() if k in allowed_keys}
    for time_key in ("quiet_start", "quiet_end", "digest_send_time"):
        if time_key in payload:
            payload[time_key] = parse_time(payload[time_key])  # TIME 欄位：需原生 datetime.time
    if payload:
        await repo.update_endpoint(ep["id"], payload)
    return await repo.get_endpoint(ep["id"])


async def disable_endpoint(endpoint_code: str, repo: Any) -> None:
    """FR-RC-08：停用保留歷史紀錄"""
    ep = await repo.get_endpoint_by_code(endpoint_code)
    if not ep:
        raise NotifyNotFoundException(f"端點不存在：{endpoint_code}")
    await repo.update_endpoint(ep["id"], {"status": "disabled"})


async def test_send(endpoint_code: str, repo: Any) -> dict:
    """UC-09：測試發送，直接呼叫管道 adapter，不經過 Outbox（不影響去重/統計）"""
    ep = await repo.get_endpoint_by_code(endpoint_code)
    if not ep:
        raise NotifyNotFoundException(f"端點不存在：{endpoint_code}")

    from notify.channel_config import decrypt_settings
    from notify.channels import get_channel

    channel_row = await repo.get_channel(ep["channel_code"])
    if not channel_row:
        return {"ok": False, "detail": "管道不存在"}

    adapter = get_channel(ep["channel_code"])
    if adapter is None:
        return {"ok": False, "detail": "未知管道"}

    settings = decrypt_settings(channel_row.get("settings_enc") or "")
    result = await adapter.send(
        subject="MyStock 測試訊息",
        body=f"這是一則測試訊息，確認「{ep['address']}」設定正確可正常接收通知。\n{DISCLAIMER}",
        address=ep["address"],
        settings=settings,
    )
    return {"ok": result.ok, "detail": result.failure_reason or "測試訊息已送出"}


# ── 授權上限（系統擁有者專用，M13 前提：管理者可見但不可代改偏好，
#    只能調整「上限」，實際選擇仍由收件人自行操作）──────────────
async def set_preference_ceiling(recipient_id: int, ceiling: dict, repo: Any) -> dict:
    pref = await repo.get_preference(recipient_id)
    if not pref:
        raise NotifyNotFoundException("此收件人尚無偏好紀錄")

    updates = {}
    for dim, col in (
        ("markets", "ceiling_markets"),
        ("strengths", "ceiling_strengths"),
        ("signal_types", "ceiling_signal_types"),
        ("strategy_categories", "ceiling_strategy_categories"),
    ):
        if dim in ceiling:
            updates[col] = ceiling[dim]
            # 上限收緊時，目前選擇同步收窄（不留下超出新上限的殘留值）
            allowed_col = col.replace("ceiling_", "allowed_")
            current_allowed = pref.get(allowed_col) or []
            updates[allowed_col] = [v for v in current_allowed if v in ceiling[dim]]

    if updates:
        await repo.upsert_preference(recipient_id, updates)
        await repo.create_preference_audit(recipient_id, "owner", {"ceiling_updated": ceiling})
    return await repo.get_preference(recipient_id)


# ── 群組 ──────────────────────────────────────────────────────
async def create_group(group_name: str, repo: Any) -> dict:
    if not group_name or not group_name.strip():
        raise NotifyValidationException("群組名稱不可為空")
    group_id = await repo.create_group({"group_code": _new_code("grp"), "group_name": group_name.strip()})
    groups = await repo.list_groups_with_members()
    return next(g for g in groups if g["id"] == group_id)


async def add_member(group_code: str, recipient_code: str, repo: Any) -> None:
    group = await repo.get_group_by_code(group_code)
    recipient = await repo.get_recipient_by_code(recipient_code)
    if not group or not recipient:
        raise NotifyNotFoundException("群組或收件人不存在")
    await repo.add_group_member(group["id"], recipient["id"])


async def remove_member(group_code: str, recipient_code: str, repo: Any) -> None:
    group = await repo.get_group_by_code(group_code)
    recipient = await repo.get_recipient_by_code(recipient_code)
    if not group or not recipient:
        raise NotifyNotFoundException("群組或收件人不存在")
    await repo.remove_group_member(group["id"], recipient["id"])
