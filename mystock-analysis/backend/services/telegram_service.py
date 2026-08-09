"""Telegram 股票警示通知服務（Application Service Layer）

負責透過 Telegram Bot API 發送 HTML 格式訊息。
不依賴 UnitOfWork，因為此服務為純外部 HTTP 呼叫，無 DB 交易邊界。

設定方式（.env 檔）：
    TELEGRAM_BOT_TOKEN=<你的 Bot Token>
    TELEGRAM_CHAT_ID=<你的 Chat ID>
"""
import logging

import httpx

from backend.core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from backend.core.exceptions import AppException
from backend.core.i18n import DEFAULT_LOCALE, translate

log = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org"


async def send_telegram_alert(
    message: str,
    parse_mode: str = "HTML",
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
    locale: str = DEFAULT_LOCALE,
) -> dict:
    """發送訊息到 Telegram Bot。

    Args:
        message:    訊息內容（支援 HTML 標籤，如 <b>粗體</b>、<i>斜體</i>）
        parse_mode: 訊息格式，"HTML" 或 "Markdown"（預設 "HTML"）
        bot_token:  Bot Token（預設從環境變數 TELEGRAM_BOT_TOKEN 讀取）
        chat_id:    Chat ID（預設從環境變數 TELEGRAM_CHAT_ID 讀取）
        locale:     回應語系（"zh-TW" 或 "zh-CN"）

    Returns:
        dict: { status, message, telegram_msg_id }

    Raises:
        AppException("TELEGRAM_NOT_CONFIGURED", 503): Token 或 Chat ID 未設定
        AppException("TELEGRAM_TIMEOUT", 504):        API 請求逾時
        AppException("TELEGRAM_REQUEST_FAILED", 502): 網路連線失敗
        AppException("TELEGRAM_SEND_FAILED", 502):    Telegram API 回傳 ok=False
    """
    if not bot_token or not chat_id:
        raise AppException("TELEGRAM_NOT_CONFIGURED", status_code=503)

    url = f"{_TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }

    log.info("[Telegram] 發送訊息 chat_id=%s parse_mode=%s", chat_id, parse_mode)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            data = response.json()
    except httpx.TimeoutException as exc:
        log.warning("[Telegram] 請求逾時: %s", exc)
        raise AppException("TELEGRAM_TIMEOUT", status_code=504) from exc
    except httpx.RequestError as exc:
        log.warning("[Telegram] 連線失敗: %s", exc)
        raise AppException("TELEGRAM_REQUEST_FAILED", status_code=502) from exc

    if not data.get("ok"):
        desc = data.get("description", "")
        log.warning("[Telegram] API 回傳錯誤: %s", desc)
        raise AppException("TELEGRAM_SEND_FAILED", status_code=502)

    msg_id: int | None = data.get("result", {}).get("message_id")
    log.info("[Telegram] 發送成功 message_id=%s", msg_id)

    return {
        "status": "success",
        "message": translate("TELEGRAM_SEND_SUCCESS", locale),
        "telegram_msg_id": msg_id,
    }
