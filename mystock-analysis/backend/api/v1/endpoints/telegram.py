"""Telegram 股票警示通知 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
因底層為異步 httpx 呼叫，故使用 async def（不同於 pyodbc 同步路由）。
本端點不需要 UnitOfWork（無 DB 交易行為）。
"""
from fastapi import APIRouter, Depends
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.schemas.weighbridge import TelegramAlertRequest
from backend.schemas.responses import TelegramAlertResponse
from backend.services.telegram_service import send_telegram_alert

router = APIRouter(
    prefix="/api/notify",
    tags=["Telegram 通知"],
    route_class=DishkaRoute,
)


@router.post("/telegram", response_model=TelegramAlertResponse)
async def api_send_telegram_alert(
    req: TelegramAlertRequest,
    locale: str = Depends(get_locale),
):
    """發送股票警示訊息到 Telegram。

    透過設定的 Bot Token 與 Chat ID 發送 HTML 格式通知訊息。

    Request Body: TelegramAlertRequest
        - message:     訊息內容（支援 HTML 標籤）
        - parse_mode:  訊息格式，預設 "HTML"

    Returns:
        { status: "success", message, telegram_msg_id }

    Errors:
        503 TELEGRAM_NOT_CONFIGURED — 環境變數未設定
        504 TELEGRAM_TIMEOUT        — API 請求逾時
        502 TELEGRAM_REQUEST_FAILED — 網路連線失敗
        502 TELEGRAM_SEND_FAILED    — Telegram API 回傳錯誤

    範例呼叫：
        await send_stock_alert("<b>股票警示</b>\\n2330 台積電 已達設定價位！")
    """
    return await send_telegram_alert(
        message=req.message,
        parse_mode=req.parse_mode,
        locale=locale,
    )
