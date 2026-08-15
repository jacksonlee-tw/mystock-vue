"""
notify/selfservice.py
M13 自助訂閱模組（§6.3 M13、§7.2、§8.7 流程）

安全前提（每個函式都必須遵守）：
- 所有操作一律以 recipient_id 為界，絕不允許跨收件人存取（AC-21）
- 「只能收窄，不能放寬」在此處對照 ceiling_* 強制驗證，不倚賴前端（FR-SS-08、AC-24）
- 暫停與退訂皆為破壞性 / 準破壞性操作，呼叫端（API 層）需自行要求二次確認
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from notify.security import (
    NotifyNotFoundException, NotifyValidationException,
    PreferenceWideningException, create_self_service_session, sha256_hex,
)
from notify.timeutil import parse_time

logger = logging.getLogger("mystock-backend")

_PAUSE_ALLOWED_DAYS = (1, 3, 7, 30)


# ── 連結核發 / 交換（ADR-09，§7.2）────────────────────────────
async def issue_link(recipient_id: int, repo: Any) -> str:
    """
    產生新的自助連結（管理端動作，FR-SS-10）。
    回傳明文 raw token —— 這是唯一會出現明文的地方，呼叫端顯示給使用者後即不可再取回（NFR-19）。
    """
    import secrets
    raw_token = secrets.token_urlsafe(32)
    await repo.create_self_service_token({
        "token_digest": sha256_hex(raw_token),
        "recipient_id": recipient_id,
    })
    logger.info("[通知] 自助連結已（重）產生 recipient_id=%s", recipient_id)
    return raw_token


async def revoke_link(recipient_id: int, repo: Any) -> None:
    await repo.revoke_self_service_token(recipient_id)
    logger.info("[通知] 自助連結已撤銷 recipient_id=%s", recipient_id)


async def exchange_token_for_session(raw_token: str, repo: Any) -> str | None:
    """
    GET /n/s/{token} 的核心邏輯：驗證 token → 換發 Cookie 值。
    成功回傳 Cookie 簽章值；失敗回傳 None（呼叫端一律回相同的 401，不透露原因，NFR-19）。
    """
    digest = sha256_hex(raw_token)
    row = await repo.get_self_service_token_by_digest(digest)
    if not row or row.get("status") != "active":
        return None

    await repo.mark_self_service_token_used(digest)
    return create_self_service_session(row["recipient_id"])


# ── 檢視（GET /me，§9.2）────────────────────────────────────────
async def get_my_view(recipient_id: int, repo: Any) -> dict:
    """
    回傳「只顯示本人資料」的完整視圖：個人端點、目前偏好、授權上限（供前端灰化）、暫停狀態。
    （FR-SS-02/03/11：不得暴露其他收件人或系統層級設定）
    """
    recipient = await repo.get_recipient(recipient_id)
    if not recipient:
        raise NotifyNotFoundException("收件人不存在")

    endpoints = await repo.list_endpoints_for_recipient(recipient_id)
    # 只回傳個人端點該有的欄位；不含任何其他收件人資訊（endpoints 本就已用 recipient_id 過濾）
    pref = await repo.get_preference(recipient_id) or {}

    return {
        "recipient": {
            "recipient_code": recipient["recipient_code"],
            "display_name":   recipient["display_name"],
        },
        "endpoints": endpoints,
        "preference": {
            "selected": {
                "markets":             pref.get("allowed_markets", []),
                "strengths":           pref.get("allowed_strengths", []),
                "signal_types":        pref.get("allowed_signal_types", []),
                "strategy_categories": pref.get("allowed_strategy_categories", []),
                "watch_symbols":       pref.get("watch_symbols"),
            },
            "ceiling": {
                "markets":             pref.get("ceiling_markets", []),
                "strengths":           pref.get("ceiling_strengths", []),
                "signal_types":        pref.get("ceiling_signal_types", []),
                "strategy_categories": pref.get("ceiling_strategy_categories", []),
            },
        },
    }


# ── 調整訂閱範圍（FR-SS-04/08，AC-22/24）────────────────────────
_DIM_MAP = {
    "markets":             ("allowed_markets", "ceiling_markets"),
    "strengths":            ("allowed_strengths", "ceiling_strengths"),
    "signal_types":         ("allowed_signal_types", "ceiling_signal_types"),
    "strategy_categories":  ("allowed_strategy_categories", "ceiling_strategy_categories"),
}


async def narrow_preferences(recipient_id: int, updates: dict, repo: Any) -> dict:
    """
    收件人自行調整訂閱範圍。每個維度的新值必須是 ceiling 的子集，
    否則整批拒絕並拋出 PreferenceWideningException（FR-SS-08，AC-24：不允許放寬）。
    watch_symbols 沒有上限概念（清單本身即是收窄），不做子集檢查。
    """
    pref = await repo.get_preference(recipient_id)
    if not pref:
        raise NotifyNotFoundException("收件人偏好尚未初始化")

    payload: dict = {}
    change_summary: dict = {}

    for dim, (allowed_col, ceiling_col) in _DIM_MAP.items():
        if dim not in updates:
            continue
        new_val = updates[dim]
        if not isinstance(new_val, list):
            raise NotifyValidationException(f"{dim} 必須為清單")
        ceiling = set(pref.get(ceiling_col) or [])
        if not set(new_val).issubset(ceiling):
            raise PreferenceWideningException(
                f"{dim} 超出系統擁有者指派的範圍：{sorted(set(new_val) - ceiling)}"
            )
        payload[allowed_col] = new_val
        change_summary[dim] = new_val

    if "watch_symbols" in updates:
        symbols = updates["watch_symbols"]
        if symbols is not None and not isinstance(symbols, list):
            raise NotifyValidationException("watch_symbols 必須為清單或 null")
        payload["watch_symbols"] = symbols
        change_summary["watch_symbols"] = symbols

    if not payload:
        return await get_my_view(recipient_id, repo)

    await repo.upsert_preference(recipient_id, payload)
    await repo.create_preference_audit(recipient_id, "self", change_summary)  # FR-SS-12
    logger.info("[通知] 收件人 %s 調整訂閱範圍：%s", recipient_id, list(change_summary.keys()))
    return await get_my_view(recipient_id, repo)


async def update_my_endpoint(recipient_id: int, endpoint_code: str, updates: dict, repo: Any) -> dict:
    """
    調整「自己」某個端點的接收節奏（FR-SS-05）。
    必須先確認該端點確實屬於這位收件人，否則視同端點不存在（AC-21：絕不能修改到他人端點）。
    """
    ep = await repo.get_endpoint_by_code(endpoint_code)
    if not ep or ep.get("recipient_id") != recipient_id:
        raise NotifyNotFoundException("端點不存在")
    if ep.get("endpoint_scope") != "personal":
        raise NotifyValidationException("共用端點不可由自助頁調整")

    allowed_keys = {"delivery_mode", "quiet_start", "quiet_end", "daily_limit"}
    payload = {k: v for k, v in updates.items() if k in allowed_keys}
    if payload:
        # DB 寫入用：TIME 欄位需原生 datetime.time（notify/timeutil.py），
        # 稽核紀錄仍用原始輸入值（字串），time 物件無法直接 json.dumps
        db_payload = dict(payload)
        for time_key in ("quiet_start", "quiet_end"):
            if time_key in db_payload:
                db_payload[time_key] = parse_time(db_payload[time_key])
        await repo.update_endpoint(ep["id"], db_payload)
        await repo.create_preference_audit(recipient_id, "self", {"endpoint": endpoint_code, **payload})
    return await repo.get_endpoint(ep["id"])


# ── 暫停 / 恢復（FR-SS-06，AC-23）────────────────────────────
async def pause(recipient_id: int, days: int, repo: Any) -> dict:
    if days not in _PAUSE_ALLOWED_DAYS:
        raise NotifyValidationException(f"暫停天數只能是 {_PAUSE_ALLOWED_DAYS} 之一")

    until = datetime.now(timezone.utc) + timedelta(days=days)
    endpoints = await repo.list_endpoints_for_recipient(recipient_id)
    for ep in endpoints:
        if ep.get("endpoint_scope") == "personal":
            await repo.update_endpoint(ep["id"], {"pause_until": until})  # TIMESTAMPTZ：需原生 datetime

    await repo.create_preference_audit(recipient_id, "self", {"paused_until": until.isoformat()})
    logger.info("[通知] 收件人 %s 暫停通知至 %s", recipient_id, until.isoformat())
    return {"pause_until": until.isoformat()}


async def resume(recipient_id: int, repo: Any) -> None:
    endpoints = await repo.list_endpoints_for_recipient(recipient_id)
    for ep in endpoints:
        if ep.get("endpoint_scope") == "personal":
            await repo.update_endpoint(ep["id"], {"pause_until": None})
    await repo.create_preference_audit(recipient_id, "self", {"paused_until": None})
    logger.info("[通知] 收件人 %s 提前恢復通知", recipient_id)


# ── 退訂（FR-SS-07，AC-17）────────────────────────────────────
async def unsubscribe(recipient_id: int, scope: str, endpoint_code: str | None, repo: Any) -> dict:
    """
    scope='endpoint'：退訂單一端點（須帶 endpoint_code，且必須屬於本人）
    scope='all'：退訂全部個人端點，立即停止發送（暫停不同，退訂不可逆，須由擁有者重新邀請）
    """
    endpoints = await repo.list_endpoints_for_recipient(recipient_id)
    personal = [e for e in endpoints if e.get("endpoint_scope") == "personal"]

    if scope == "endpoint":
        if not endpoint_code:
            raise NotifyValidationException("scope=endpoint 時必須提供 endpoint_code")
        target = next((e for e in personal if e["endpoint_code"] == endpoint_code), None)
        if not target:
            raise NotifyNotFoundException("端點不存在")
        await repo.update_endpoint(target["id"], {"status": "unsubscribed"})
        unsubscribed = [endpoint_code]
    elif scope == "all":
        unsubscribed = []
        for ep in personal:
            await repo.update_endpoint(ep["id"], {"status": "unsubscribed"})
            unsubscribed.append(ep["endpoint_code"])
    else:
        raise NotifyValidationException("scope 必須為 endpoint 或 all")

    await repo.create_preference_audit(recipient_id, "self", {"unsubscribed": unsubscribed})
    logger.info("[通知] 收件人 %s 退訂：%s", recipient_id, unsubscribed)
    return {"unsubscribed": unsubscribed}


# ── 我收到的通知（FR-SS-09）──────────────────────────────────
async def my_recent_messages(recipient_id: int, repo: Any, days: int = 7) -> list[dict]:
    return await repo.list_messages_for_recipient(recipient_id, days=days)
