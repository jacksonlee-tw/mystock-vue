"""
notify/binding.py
M9 綁定驗證（§7.4）
- Email 驗證 token：寄驗證信，使用者點擊後端點設 verify_status=verified
- Telegram 綁定碼：4-digit code，使用者在 Telegram 發給 bot
"""
from __future__ import annotations
import logging
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from notify import config as notify_config
from notify.security import sha256_hex

logger = logging.getLogger("mystock-backend")

# 綁定碼：4 位數字（Telegram）
_BIND_CODE_CHARS = string.digits
_BIND_CODE_TTL_MIN = 15  # 15 分鐘有效


def _generate_token() -> str:
    """URL-safe 安全 token（Email 驗證，32 bytes）"""
    return secrets.token_urlsafe(32)


def _generate_binding_code() -> str:
    """4 位數綁定碼（Telegram）"""
    return "".join(random.choices(_BIND_CODE_CHARS, k=4))


async def issue_email_verification(
    endpoint_id: int,
    recipient_id: int,
    email_address: str,
    repo: Any,
) -> str:
    """
    建立 Email 驗證 token（purpose='email_verify'）。
    回傳驗證 URL 供 UI 顯示或直接寄出。
    """
    raw_token = _generate_token()
    token_digest = sha256_hex(raw_token)
    expires_at   = datetime.now(timezone.utc) + timedelta(hours=24)

    await repo.create_binding_token({
        "token_digest": token_digest,
        "purpose":      "email_verify",
        "channel_code": "email",
        "endpoint_id":  endpoint_id,
        "recipient_id": recipient_id,
        "expires_at":   expires_at,  # TIMESTAMPTZ 欄位：asyncpg 需要原生 datetime 物件，不可傳字串
    })

    base_url = notify_config.get_public_base_url().rstrip("/")
    verify_url = f"{base_url}/n/v/{raw_token}"
    logger.info("[通知] Email 驗證 token 已建立 ep_id=%s", endpoint_id)
    return verify_url


async def issue_binding_code(
    recipient_id: int | None,
    repo: Any,
) -> str:
    """
    建立 Telegram 綁定碼（purpose='telegram_bind'）。
    此時尚無 endpoint——Telegram 的收件位址（chat_id）要等使用者在對話中送出綁定碼、
    機器人收到 webhook/polling 更新後才知道，因此端點是綁定「成功後」才建立
    （見 notify/telegram_bot.py，對應需求規格書 §8.2 序列圖）。

    recipient_id=None 代表這是「共用端點（群組）」的綁定碼：綁定成功後建立
    endpoint_scope='shared' 的端點，不屬於任何收件人（FR-RC-09、RK-10）。
    recipient_id 給值則代表個人綁定，成功後建立該收件人的個人端點。
    """
    raw_code = _generate_binding_code()
    token_digest = sha256_hex(raw_code)
    expires_at   = datetime.now(timezone.utc) + timedelta(minutes=_BIND_CODE_TTL_MIN)

    await repo.create_binding_token({
        "token_digest": token_digest,
        "purpose":      "telegram_bind",
        "channel_code": "telegram",
        "endpoint_id":  None,
        "recipient_id": recipient_id,
        "expires_at":   expires_at,  # TIMESTAMPTZ 欄位：asyncpg 需要原生 datetime 物件，不可傳字串
    })

    logger.info("[通知] Telegram 綁定碼已建立 recipient_id=%s", recipient_id)
    return raw_code


async def consume_token(
    raw_token: str,
    purpose: str,
    repo: Any,
) -> dict | None:
    """
    驗證並消費 token（single-use）。
    成功回傳 binding_token row；失敗或過期回傳 None。
    """
    token_digest = sha256_hex(raw_token)
    row = await repo.get_binding_token(token_digest)
    if not row:
        logger.info("[通知] Token 不存在或已使用（purpose=%s）", purpose)
        return None

    if row.get("purpose") != purpose:
        logger.warning("[通知] Token purpose 不符：期望 %s，實際 %s", purpose, row.get("purpose"))
        return None

    # 過期檢查
    expires_at = row.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(str(expires_at))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                logger.info("[通知] Token 已過期（purpose=%s）", purpose)
                return None
        except Exception:
            pass

    await repo.consume_binding_token(token_digest)
    logger.info("[通知] Token 已消費（purpose=%s，ep_id=%s）", purpose, row.get("endpoint_id"))
    return row
