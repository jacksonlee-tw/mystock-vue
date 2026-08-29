"""
api/v1/endpoints/notify_admin.py
整合訊息通知平台 — 管理端 API（§6.2 ①）
全部端點皆需 require_owner 授權（FR-AU-01/02、NFR-22）；寫入型端點另寫入 notify_admin_audit（FR-AU-03）。
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from db.session import get_db
from repositories.notify_repository import NotifyRepository
from core.owner_auth import (
    COOKIE_NAME, create_owner_session_token, get_owner_session_ttl_hours,
    require_owner, set_owner_password, verify_owner_password,
)
from notify import config as notify_config
from notify.security import (
    mask_settings, NotifyNotFoundException, NotifyValidationException,
)

router = APIRouter(
    prefix="/api/v1/notify",
    tags=["Notify Admin"],
    dependencies=[Depends(require_owner)],
)

# Session 本身不能要求已登入，另掛一個沒有 dependency 的 router。
session_router = APIRouter(prefix="/api/v1", tags=["Owner Session"])


def envelope(data: Any = None, message: str | None = None) -> dict:
    body = {"success": True, "data": data}
    if message:
        body["message"] = message
    return body


async def _audit(repo: NotifyRepository, actor: str, action: str, target: str, result: str, detail: dict | None = None) -> None:
    try:
        await repo.log_admin_action(actor, action, target, result, detail)
    except Exception:
        pass  # 稽核紀錄失敗不得影響主要操作（比照鐵則 R7 的容錯精神）


# ────────────────────────────────────────────────────────────
# 登入（不受 require_owner 保護，本身就是取得授權的手段）
# ────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _set_owner_cookie(response: Response) -> None:
    response.set_cookie(
        COOKIE_NAME, create_owner_session_token(), httponly=True, samesite="lax",
        secure=not notify_config.allow_insecure_cookie(),
        max_age=get_owner_session_ttl_hours() * 3600,
    )


@session_router.post("/notify/session", include_in_schema=False)
@session_router.post("/auth/session", summary="系統擁有者登入")
async def login(req: LoginRequest, response: Response):
    if not verify_owner_password(req.password):
        return {"success": False, "error": {"code": "OWNER_UNAUTHORIZED", "message": "密碼錯誤"}}
    _set_owner_cookie(response)
    return envelope({"authenticated": True})


@session_router.put("/auth/password", summary="變更系統擁有者密碼")
async def change_password(req: ChangePasswordRequest, response: Response):
    if not verify_owner_password(req.current_password):
        return {"success": False, "error": {"code": "OWNER_UNAUTHORIZED", "message": "原密碼錯誤"}}
    if len(req.new_password) < 8:
        return {"success": False, "error": {"code": "INVALID_PASSWORD", "message": "新密碼至少需要 8 個字元"}}

    set_owner_password(req.new_password)
    _set_owner_cookie(response)
    return envelope({"authenticated": True}, "密碼已變更")


@session_router.delete("/notify/session", include_in_schema=False)
@session_router.delete("/auth/session", summary="系統擁有者登出")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return envelope({"authenticated": False})


@session_router.get("/notify/session", dependencies=[Depends(require_owner)], include_in_schema=False)
@session_router.get("/auth/session", dependencies=[Depends(require_owner)], summary="檢查目前是否已登入")
async def whoami():
    return envelope({"authenticated": True})


# ────────────────────────────────────────────────────────────
# ① 管道設定
# ────────────────────────────────────────────────────────────
@router.get("/channels", summary="管道清單與健康狀態")
async def list_channels(db=Depends(get_db)):
    repo = NotifyRepository(db)
    channels = await repo.list_channels()
    for c in channels:
        settings = {}
        if c.get("settings_enc"):
            from notify.channel_config import decrypt_settings
            settings = decrypt_settings(c["settings_enc"])
        c["settings"] = mask_settings(settings)
        c.pop("settings_enc", None)
    return envelope(channels)


@router.get("/channels/{code}", summary="單一管道設定（機敏欄位遮蔽）")
async def get_channel(code: str, db=Depends(get_db)):
    repo = NotifyRepository(db)
    channel = await repo.get_channel(code)
    if not channel:
        raise NotifyNotFoundException(f"管道不存在：{code}")
    settings = {}
    if channel.get("settings_enc"):
        from notify.channel_config import decrypt_settings
        settings = decrypt_settings(channel["settings_enc"])
    channel["settings"] = mask_settings(settings)
    channel.pop("settings_enc", None)
    return envelope(channel)


class ChannelSettingsRequest(BaseModel):
    settings: dict


@router.put("/channels/{code}", summary="更新管道設定（機敏欄位傳 null 代表保留原值）")
async def update_channel(code: str, req: ChannelSettingsRequest, db=Depends(get_db)):
    from notify.channel_config import encrypt_settings, decrypt_settings, validate_channel_settings

    repo = NotifyRepository(db)
    channel = await repo.get_channel(code)
    if not channel:
        raise NotifyNotFoundException(f"管道不存在：{code}")

    current = decrypt_settings(channel.get("settings_enc") or "")
    merged = {**current}
    for k, v in req.settings.items():
        if v is not None:
            merged[k] = v

    errors = validate_channel_settings(code, merged)
    status = "misconfigured" if errors else channel.get("status", "disabled")
    if status == "misconfigured":
        pass
    elif status not in ("enabled", "disabled", "circuit_open"):
        status = "disabled"

    await repo.update_channel(code, {
        "settings_enc": encrypt_settings(merged),
        "status": status,
    })
    await _audit(repo, "owner", "update_channel", code, "success" if not errors else "failure",
                 {"errors": errors} if errors else None)
    return envelope({"errors": errors}, "設定已更新" if not errors else "設定不完整")


@router.post("/channels/{code}/enable", summary="啟用管道")
async def enable_channel(code: str, db=Depends(get_db)):
    from notify.channel_config import decrypt_settings, validate_channel_settings
    repo = NotifyRepository(db)
    channel = await repo.get_channel(code)
    if not channel:
        raise NotifyNotFoundException(f"管道不存在：{code}")
    settings = decrypt_settings(channel.get("settings_enc") or "")
    errors = validate_channel_settings(code, settings)
    new_status = "misconfigured" if errors else "enabled"
    await repo.update_channel(code, {"status": new_status})
    await _audit(repo, "owner", "enable_channel", code, "success" if not errors else "failure")
    return envelope({"status": new_status, "errors": errors})


@router.post("/channels/{code}/disable", summary="停用管道")
async def disable_channel(code: str, db=Depends(get_db)):
    repo = NotifyRepository(db)
    channel = await repo.get_channel(code)
    if not channel:
        raise NotifyNotFoundException(f"管道不存在：{code}")
    await repo.update_channel(code, {"status": "disabled"})
    await _audit(repo, "owner", "disable_channel", code, "success")
    return envelope({"status": "disabled"}, f"已停用 {code}，其他管道不受影響")


@router.post("/channels/{code}/test", summary="連線測試（不寫入訊息單，UC-09）")
async def test_channel(code: str, db=Depends(get_db)):
    from notify.channel_config import decrypt_settings, test_connection
    repo = NotifyRepository(db)
    channel = await repo.get_channel(code)
    if not channel:
        raise NotifyNotFoundException(f"管道不存在：{code}")
    settings = decrypt_settings(channel.get("settings_enc") or "")
    result = await test_connection(code, settings, repo)
    await repo.update_channel(code, {
        "last_health_at": datetime.now(timezone.utc),  # TIMESTAMPTZ：需原生 datetime
        "last_health_detail": (result.get("detail") or "")[:200],
    })
    return envelope(result)


# ────────────────────────────────────────────────────────────
# ② 收件人管理
# ────────────────────────────────────────────────────────────
@router.get("/recipients", summary="收件人清單")
async def list_recipients(db=Depends(get_db)):
    repo = NotifyRepository(db)
    recipients = await repo.list_recipients_with_groups()
    for r in recipients:
        r["endpoints"] = await repo.list_endpoints_for_recipient(r["id"])
    return envelope(recipients)


class RecipientCreateRequest(BaseModel):
    display_name: str
    group_codes: list[str] = []


@router.post("/recipients", summary="新增收件人")
async def create_recipient_ep(req: RecipientCreateRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    recipient = await recipients_mod.create_recipient(req.display_name, req.group_codes, repo)
    await _audit(repo, "owner", "create_recipient", recipient["recipient_code"], "success")
    return envelope(recipient, "已新增收件人")


class RecipientUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    status: Optional[str] = None


@router.patch("/recipients/{code}", summary="編輯收件人")
async def update_recipient_ep(code: str, req: RecipientUpdateRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    await recipients_mod.update_recipient(recipient["id"], req.model_dump(exclude_none=True), repo)
    await _audit(repo, "owner", "update_recipient", code, "success")
    return envelope(await repo.get_recipient(recipient["id"]), "已更新")


@router.delete("/recipients/{code}", summary="停用收件人（保留歷史紀錄，FR-RC-08）")
async def disable_recipient_ep(code: str, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    await recipients_mod.disable_recipient(recipient["id"], repo)
    await _audit(repo, "owner", "disable_recipient", code, "success")
    return envelope(None, "已停用")


@router.get("/recipients/{code}/preferences", summary="檢視收件人自助偏好（唯讀）")
async def get_recipient_preferences(code: str, db=Depends(get_db)):
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    pref = await repo.get_preference(recipient["id"])
    audit = await repo.list_preference_audit(recipient["id"])
    return envelope({"preference": pref, "audit": audit})


class CeilingUpdateRequest(BaseModel):
    markets: Optional[list[str]] = None
    strengths: Optional[list[str]] = None
    signal_types: Optional[list[str]] = None
    strategy_categories: Optional[list[str]] = None


@router.put("/recipients/{code}/ceiling", summary="調整收件人的授權上限（只有擁有者能調整，非代改偏好）")
async def update_ceiling(code: str, req: CeilingUpdateRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    pref = await recipients_mod.set_preference_ceiling(recipient["id"], req.model_dump(exclude_none=True), repo)
    await _audit(repo, "owner", "update_ceiling", code, "success", req.model_dump(exclude_none=True))
    return envelope(pref, "授權上限已更新")


@router.post("/recipients/{code}/self-service-link", summary="產生／撤銷重產專屬連結（明文只回傳這一次，FR-SS-10）")
async def issue_self_service_link(code: str, db=Depends(get_db)):
    from notify import selfservice
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    raw_token = await selfservice.issue_link(recipient["id"], repo)
    base = notify_config.get_public_base_url().rstrip("/")
    await _audit(repo, "owner", "issue_self_service_link", code, "success")
    return envelope({"url": f"{base}/n/s/{raw_token}"}, "新連結已產生；舊連結已立即失效，此網址只會顯示這一次")


@router.delete("/recipients/{code}/self-service-link", summary="僅撤銷（不重新產生）")
async def revoke_self_service_link(code: str, db=Depends(get_db)):
    from notify import selfservice
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    await selfservice.revoke_link(recipient["id"], repo)
    await _audit(repo, "owner", "revoke_self_service_link", code, "success")
    return envelope(None, "已撤銷")


class EmailEndpointRequest(BaseModel):
    address: str
    delivery_mode: str = "digest"
    daily_limit: int = 30


class SlackEndpointRequest(BaseModel):
    address: str
    delivery_mode: str = "realtime"
    daily_limit: int = 30


@router.post("/recipients/{code}/endpoints/email", summary="新增 Email 端點並產生驗證連結（FR-BD-01）")
async def create_email_endpoint(code: str, req: EmailEndpointRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod, binding
    repo = NotifyRepository(db)
    ep = await recipients_mod.create_personal_endpoint(
        code, "email", req.address, repo,
        delivery_mode=req.delivery_mode, daily_limit=req.daily_limit,
    )
    recipient = await repo.get_recipient_by_code(code)
    verify_url = await binding.issue_email_verification(ep["id"], recipient["id"], req.address, repo)
    await _audit(repo, "owner", "create_email_endpoint", ep["endpoint_code"], "success")
    # Phase 1：驗證信實際寄送交由 Email 管道發送（此處僅回傳連結，供未接妥 SMTP 前也能手動驗證測試）
    return envelope({"endpoint": ep, "verify_url": verify_url}, "已建立，驗證連結於 24 小時內有效")


@router.post("/recipients/{code}/endpoints/slack", summary="新增 Slack 收件端點")
async def create_slack_endpoint(code: str, req: SlackEndpointRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    if not req.address.strip():
        raise NotifyValidationException("Slack 目的地名稱不可為空")
    ep = await recipients_mod.create_personal_endpoint(
        code, "slack", req.address, repo,
        delivery_mode=req.delivery_mode, daily_limit=req.daily_limit,
    )
    await repo.update_endpoint(ep["id"], {"verify_status": "verified"})
    ep = await repo.get_endpoint(ep["id"])
    await _audit(repo, "owner", "create_slack_endpoint", ep["endpoint_code"], "success")
    return envelope(ep, "已建立 Slack 收件端點")


@router.post("/recipients/{code}/endpoints/{endpoint_code}/resend-verification", summary="重新產生驗證連結")
async def resend_verification(code: str, endpoint_code: str, db=Depends(get_db)):
    from notify import binding
    repo = NotifyRepository(db)
    ep = await repo.get_endpoint_by_code(endpoint_code)
    recipient = await repo.get_recipient_by_code(code)
    if not ep or not recipient or ep.get("recipient_id") != recipient["id"]:
        raise NotifyNotFoundException("端點不存在")
    verify_url = await binding.issue_email_verification(ep["id"], recipient["id"], ep["address"], repo)
    await _audit(repo, "owner", "resend_verification", endpoint_code, "success")
    return envelope({"verify_url": verify_url}, "已重新產生驗證連結")


@router.post("/recipients/{code}/binding-code", summary="產生 Telegram 一次性綁定碼（15 分鐘，FR-BD-03/04）")
async def issue_binding_code_ep(code: str, db=Depends(get_db)):
    from notify import binding
    repo = NotifyRepository(db)
    recipient = await repo.get_recipient_by_code(code)
    if not recipient:
        raise NotifyNotFoundException(f"收件人不存在：{code}")
    bind_code = await binding.issue_binding_code(recipient["id"], repo)
    await _audit(repo, "owner", "issue_binding_code", code, "success")
    return envelope({"code": bind_code, "ttl_minutes": 15})


@router.post("/binding-code/group", summary="產生 Telegram 群組（共用端點）綁定碼")
async def issue_group_binding_code_ep(db=Depends(get_db)):
    from notify import binding
    repo = NotifyRepository(db)
    bind_code = await binding.issue_binding_code(None, repo)
    await _audit(repo, "owner", "issue_group_binding_code", "-", "success")
    return envelope({"code": bind_code, "ttl_minutes": 15})


# ────────────────────────────────────────────────────────────
# 端點（含共用端點）
# ────────────────────────────────────────────────────────────
@router.get("/endpoints/shared", summary="共用端點清單（Telegram 群組等，FR-RC-09）")
async def list_shared_endpoints(db=Depends(get_db)):
    repo = NotifyRepository(db)
    return envelope(await repo.list_shared_endpoints())


class EndpointPreferenceRequest(BaseModel):
    delivery_mode: Optional[str] = None
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None
    timezone: Optional[str] = None
    daily_limit: Optional[int] = None
    digest_send_time: Optional[str] = None
    fallback_endpoint_id: Optional[int] = None


@router.patch("/endpoints/{code}", summary="端點偏好設定（模式／靜音／上限／時區／摘要時間／備援，FR-RC-06/10）")
async def update_endpoint_ep(code: str, req: EndpointPreferenceRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    ep = await recipients_mod.set_endpoint_preferences(code, req.model_dump(exclude_none=True), repo)
    await _audit(repo, "owner", "update_endpoint", code, "success")
    return envelope(ep, "已更新")


@router.post("/endpoints/{code}/test-send", summary="測試發送（UC-09，不經 Outbox）")
async def test_send_ep(code: str, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    result = await recipients_mod.test_send(code, repo)
    await _audit(repo, "owner", "test_send", code, "success" if result.get("ok") else "failure")
    return envelope(result)


@router.post("/endpoints/{code}/disable", summary="停用端點（保留歷史紀錄，FR-RC-08）")
async def disable_endpoint_ep(code: str, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    await recipients_mod.disable_endpoint(code, repo)
    await _audit(repo, "owner", "disable_endpoint", code, "success")
    return envelope(None, "已停用")


# ────────────────────────────────────────────────────────────
# 收件群組
# ────────────────────────────────────────────────────────────
@router.get("/groups", summary="收件群組清單（含成員）")
async def list_groups_ep(db=Depends(get_db)):
    repo = NotifyRepository(db)
    return envelope(await repo.list_groups_with_members())


class GroupCreateRequest(BaseModel):
    group_name: str


@router.post("/groups", summary="新增收件群組")
async def create_group_ep(req: GroupCreateRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    group = await recipients_mod.create_group(req.group_name, repo)
    await _audit(repo, "owner", "create_group", group["group_code"], "success")
    return envelope(group, "已建立")


class GroupMemberRequest(BaseModel):
    recipient_code: str


@router.post("/groups/{code}/members", summary="加入群組成員")
async def add_group_member_ep(code: str, req: GroupMemberRequest, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    await recipients_mod.add_member(code, req.recipient_code, repo)
    await _audit(repo, "owner", "add_group_member", f"{code}:{req.recipient_code}", "success")
    return envelope(None, "已加入")


@router.delete("/groups/{code}/members/{recipient_code}", summary="移除群組成員")
async def remove_group_member_ep(code: str, recipient_code: str, db=Depends(get_db)):
    from notify import recipients as recipients_mod
    repo = NotifyRepository(db)
    await recipients_mod.remove_member(code, recipient_code, repo)
    await _audit(repo, "owner", "remove_group_member", f"{code}:{recipient_code}", "success")
    return envelope(None, "已移除")


# ────────────────────────────────────────────────────────────
# ③ 訂閱規則
# ────────────────────────────────────────────────────────────
@router.get("/subscriptions", summary="訂閱規則清單")
async def list_subscriptions_ep(db=Depends(get_db)):
    repo = NotifyRepository(db)
    return envelope(await repo.list_all_subscriptions())


class SubscriptionCreateRequest(BaseModel):
    rule_name: str
    event_type: str
    filter_conditions: dict = {}
    target_group_code: Optional[str] = None
    target_recipient_code: Optional[str] = None
    target_endpoint_code: Optional[str] = None
    priority: int = 100


@router.post("/subscriptions", summary="新增訂閱規則（目標三選一：群組／收件人／單一端點）")
async def create_subscription_ep(req: SubscriptionCreateRequest, db=Depends(get_db)):
    import uuid
    repo = NotifyRepository(db)

    target_count = sum(x is not None for x in (req.target_group_code, req.target_recipient_code, req.target_endpoint_code))
    if target_count != 1:
        raise NotifyValidationException("目標對象必須且只能指定一種：群組、收件人或單一端點")

    target_group_id = target_recipient_id = target_endpoint_id = None
    if req.target_group_code:
        g = await repo.get_group_by_code(req.target_group_code)
        if not g:
            raise NotifyNotFoundException("目標群組不存在")
        target_group_id = g["id"]
    elif req.target_recipient_code:
        r = await repo.get_recipient_by_code(req.target_recipient_code)
        if not r:
            raise NotifyNotFoundException("目標收件人不存在")
        target_recipient_id = r["id"]
    else:
        e = await repo.get_endpoint_by_code(req.target_endpoint_code)
        if not e:
            raise NotifyNotFoundException("目標端點不存在")
        target_endpoint_id = e["id"]

    sub_id = await repo.create_subscription({
        "rule_code":           f"sub-{uuid.uuid4().hex[:10]}",
        "rule_name":           req.rule_name,
        "event_type":          req.event_type,
        "filter_conditions":   req.filter_conditions,
        "target_group_id":     target_group_id,
        "target_recipient_id": target_recipient_id,
        "target_endpoint_id":  target_endpoint_id,
        "status":              "enabled",
        "priority":            req.priority,
    })
    await _audit(repo, "owner", "create_subscription", str(sub_id), "success")
    subs = await repo.list_all_subscriptions()
    return envelope(next(s for s in subs if s["id"] == sub_id), "已建立")


class SubscriptionUpdateRequest(BaseModel):
    rule_name: Optional[str] = None
    filter_conditions: Optional[dict] = None
    status: Optional[str] = None
    priority: Optional[int] = None


@router.patch("/subscriptions/{code}", summary="編輯規則／啟用停用")
async def update_subscription_ep(code: str, req: SubscriptionUpdateRequest, db=Depends(get_db)):
    repo = NotifyRepository(db)
    sub = await repo.get_subscription_by_code(code)
    if not sub:
        raise NotifyNotFoundException(f"規則不存在：{code}")
    await repo.update_subscription(sub["id"], req.model_dump(exclude_none=True))
    await _audit(repo, "owner", "update_subscription", code, "success")
    return envelope(await repo.get_subscription_by_code(code), "已更新")


class SubscriptionPreviewRequest(BaseModel):
    rule_code: str
    event_type: str
    sample_facts: dict


@router.post("/subscriptions/preview", summary="規則測試：預覽是否命中（UC-06/UC-10，不寫入任何資料）")
async def preview_subscription_ep(req: SubscriptionPreviewRequest, db=Depends(get_db)):
    from notify.routing import preview_subscription
    repo = NotifyRepository(db)
    result = await preview_subscription(req.rule_code, req.event_type, req.sample_facts, repo)
    return envelope(result)


# ────────────────────────────────────────────────────────────
# ④ 訊息模板
# ────────────────────────────────────────────────────────────
@router.get("/templates", summary="模板矩陣（事件類型 × 管道）")
async def list_templates_ep(db=Depends(get_db)):
    from notify.events import EventType
    repo = NotifyRepository(db)
    existing = await repo.list_templates()
    existing_map = {(t["event_type"], t["channel_code"]): t for t in existing}

    channels = await repo.list_channels()
    matrix = []
    for et in EventType:
        for c in channels:
            key = (et.value, c["channel_code"])
            tpl = existing_map.get(key)
            matrix.append({
                "event_type":   et.value,
                "channel_code": c["channel_code"],
                "has_custom":   tpl is not None and bool(tpl.get("body_format")),
                "template":     tpl,
            })
    return envelope(matrix)


@router.get("/templates/{event_type}/{channel}", summary="取得模板內容")
async def get_template_ep(event_type: str, channel: str, db=Depends(get_db)):
    repo = NotifyRepository(db)
    tpl = await repo.get_template(event_type, channel)
    return envelope(tpl)


class TemplateUpdateRequest(BaseModel):
    title_format: Optional[str] = None
    body_format: str
    body_kind: str = "text"


@router.put("/templates/{event_type}/{channel}", summary="編輯模板（鐵則 R4：不影響任何流程邏輯）")
async def update_template_ep(event_type: str, channel: str, req: TemplateUpdateRequest, db=Depends(get_db)):
    repo = NotifyRepository(db)
    await repo.upsert_template({
        "template_code": f"{event_type}__{channel}",
        "event_type":    event_type,
        "channel_code":  channel,
        "title_format":  req.title_format,
        "body_format":   req.body_format,
        "body_kind":     req.body_kind,
    })
    await _audit(repo, "owner", "update_template", f"{event_type}/{channel}", "success")
    return envelope(await repo.get_template(event_type, channel), "模板已儲存")


@router.get("/templates/variables/{event_type}", summary="可用變數清單（FR-MC-07）")
async def get_template_variables(event_type: str):
    from notify.events import TEMPLATE_CONTEXT_SPEC
    return envelope(TEMPLATE_CONTEXT_SPEC.get(event_type, []))


class TemplatePreviewRequest(BaseModel):
    event_type: str
    channel_code: str
    title_format: Optional[str] = None
    body_format: str


@router.post("/templates/preview", summary="以範例資料渲染預覽（不落地，FR-MC-07）")
async def preview_template_ep(req: TemplatePreviewRequest, db=Depends(get_db)):
    from notify.events import SAMPLE_PAYLOADS
    from notify.templating import preview
    repo = NotifyRepository(db)
    sample = SAMPLE_PAYLOADS.get(req.event_type, {})
    extra_ctx = {
        "chart_url": "https://mystock.local/stock/tw/2330",
        "manage_url": "https://mystock.local/n/me",
        "occurred_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    result = await preview(req.event_type, req.channel_code, req.body_format, req.title_format, sample, extra_ctx, repo)
    return envelope(result)


# ────────────────────────────────────────────────────────────
# ⑤ 發送紀錄
# ────────────────────────────────────────────────────────────
@router.get("/messages", summary="發送紀錄查詢（FR-LG-02）")
async def list_messages_ep(
    status: Optional[str] = None, channel_code: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    limit: int = 50, offset: int = 0, db=Depends(get_db),
):
    repo = NotifyRepository(db)
    rows = await repo.query_messages({
        "status": status, "channel_code": channel_code,
        "date_from": date_from, "date_to": date_to,
        "limit": limit, "offset": offset,
    })
    return envelope(rows)


@router.get("/messages/{code}", summary="單筆詳情＋完整投遞歷程（FR-LG-01/03）")
async def get_message_ep(code: str, db=Depends(get_db)):
    repo = NotifyRepository(db)
    msg = await repo.get_message_by_code(code)
    if not msg:
        raise NotifyNotFoundException(f"訊息不存在：{code}")
    logs = await repo.get_delivery_logs(msg["id"])
    return envelope({"message": msg, "logs": logs})


@router.post("/messages/{code}/resend", summary="手動重送（沿用同一列，FR-LG-04、AC-14）")
async def resend_message_ep(code: str, db=Depends(get_db)):
    repo = NotifyRepository(db)
    msg = await repo.get_message_by_code(code)
    if not msg:
        raise NotifyNotFoundException(f"訊息不存在：{code}")
    if msg["status"] not in ("dead", "failed"):
        raise NotifyValidationException("只有失敗或最終失敗的訊息可以重送")
    await repo.resend_message(msg["id"])
    await _audit(repo, "owner", "resend_message", code, "success")
    return envelope(None, "已重新排入發送佇列")


@router.post("/messages/resend-failed", summary="批次重送當日失敗（FR-LG-04）")
async def resend_all_failed_ep(db=Depends(get_db)):
    repo = NotifyRepository(db)
    rows = await repo.query_messages({"status": "dead", "limit": 200, "offset": 0})
    for r in rows:
        await repo.resend_message(r["id"])
    await _audit(repo, "owner", "resend_all_failed", "-", "success", {"count": len(rows)})
    return envelope({"resent": len(rows)}, f"已重新排入 {len(rows)} 則失敗訊息")


@router.get("/stats", summary="發送統計（FR-LG-05）")
async def stats_ep(db=Depends(get_db)):
    repo = NotifyRepository(db)
    overall = await repo.stats()
    by_channel = await repo.stats_by_channel()
    ranking = await repo.failure_ranking()
    return envelope({"overall": overall, "by_channel": by_channel, "failure_ranking": ranking})


# ────────────────────────────────────────────────────────────
# 手動注入事件（測試用）
# ────────────────────────────────────────────────────────────
class ManualEventRequest(BaseModel):
    event_type: str
    severity: str = "info"
    payload: dict = {}
    source_event_key: Optional[str] = None


@router.post("/events", summary="手動注入事件（測試用；拒收 ALERT_DIGEST）")
async def inject_event_ep(req: ManualEventRequest, db=Depends(get_db)):
    from notify.events import Event, EventType
    from notify import intake

    if req.event_type == EventType.ALERT_DIGEST:
        raise NotifyValidationException("ALERT_DIGEST 只能由摘要排程內部產生，不接受外部注入")

    repo = NotifyRepository(db)
    ev = Event(
        event_type=req.event_type, severity=req.severity, source="manual",
        occurred_at=datetime.now(timezone.utc), payload=req.payload,
        source_event_key=req.source_event_key,
    )
    result = await intake.publish(ev, db)
    await _audit(repo, "owner", "inject_event", req.event_type, "success")
    return envelope(result)


# ────────────────────────────────────────────────────────────
# 管理端稽核紀錄
# ────────────────────────────────────────────────────────────
@router.get("/audit", summary="管理端操作稽核查詢（FR-AU-03）")
async def list_audit_ep(limit: int = 100, db=Depends(get_db)):
    repo = NotifyRepository(db)
    return envelope(await repo.list_admin_audit(limit))
