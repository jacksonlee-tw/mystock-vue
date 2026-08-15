"""
api/v1/endpoints/notify_public.py
整合訊息通知平台 — 公開端點（§6.2 ③）
不需授權，但一律有速率限制，且錯誤回應不得透露收件人是否存在（NFR-19）。
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse

from db.session import get_async_session
from repositories.notify_repository import NotifyRepository
from notify import config as notify_config
from notify.security import token_rate_limiter

logger = logging.getLogger("mystock-backend")

router = APIRouter(tags=["Notify Public"])

_UNAUTHORIZED_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>連結已失效</title></head><body style="font-family:sans-serif;text-align:center;padding:3rem">
<h2>連結已失效或不存在</h2><p>請向系統擁有者索取新的連結。</p></body></html>"""

_VERIFIED_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>驗證成功</title></head><body style="font-family:sans-serif;text-align:center;padding:3rem">
<h2>Email 驗證成功</h2><p>此信箱將開始接收 MyStock 通知。您可以關閉此頁面。</p></body></html>"""


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/n/s/{token}", summary="自助連結入口：驗證 token → 種 Cookie → 303 轉址（ADR-09）")
async def self_service_entry(token: str, request: Request):
    if not token_rate_limiter.check(_client_key(request)):
        return HTMLResponse(_UNAUTHORIZED_HTML, status_code=429)

    from notify import selfservice
    async with get_async_session() as session:
        repo = NotifyRepository(session)
        cookie_value = await selfservice.exchange_token_for_session(token, repo)
        await session.commit()

    if not cookie_value:
        return HTMLResponse(_UNAUTHORIZED_HTML, status_code=401)

    resp = RedirectResponse(url="/n/me", status_code=303)
    resp.set_cookie(
        "ns_session", cookie_value, httponly=True, samesite="lax",
        secure=not notify_config.allow_insecure_cookie(),
        max_age=1800,
    )
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cache-Control"] = "no-store, private"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@router.get("/n/v/{token}", summary="Email 驗證連結（一次性、24 小時，FR-BD-01/02）")
async def email_verify_entry(token: str, request: Request):
    if not token_rate_limiter.check(_client_key(request)):
        return HTMLResponse(_UNAUTHORIZED_HTML, status_code=429)

    from notify import binding
    async with get_async_session() as session:
        repo = NotifyRepository(session)
        row = await binding.consume_token(token, "email_verify", repo)
        if row and row.get("endpoint_id"):
            await repo.update_endpoint(row["endpoint_id"], {"verify_status": "verified"})
        await session.commit()

    if not row:
        return HTMLResponse(_UNAUTHORIZED_HTML, status_code=401)

    resp = HTMLResponse(_VERIFIED_HTML)
    resp.headers["Cache-Control"] = "no-store, private"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@router.post("/api/v1/notify/telegram/webhook/{secret}", summary="Telegram webhook（僅 TELEGRAM_WEBHOOK_BASE 設定時使用，ADR-06）")
async def telegram_webhook(secret: str, request: Request):
    expected = notify_config.get_telegram_webhook_secret()
    if not expected or secret != expected:
        return Response(status_code=404)  # 不洩漏端點是否存在

    from notify.telegram_bot import process_update
    update = await request.json()
    async with get_async_session() as session:
        repo = NotifyRepository(session)
        try:
            await process_update(update, repo)
            await session.commit()
        except Exception as exc:
            logger.warning("[通知] Telegram webhook 處理失敗（已靜默）：%s", exc)
    return Response(status_code=200)
