"""
notify/channels/email_channel.py
Email 管道轉接器（ADR-05：aiosmtplib 非同步 SMTP）
"""
from __future__ import annotations
import json
import logging
import time
from email.message import EmailMessage

from . import channel
from .base import ChannelAdapter, Capability, SendResult, FailureKind, HealthResult
from notify import config as notify_config

logger = logging.getLogger("mystock-backend")

_PERMANENT_SMTP_CODES = {550, 551, 552, 553, 554, 555}
_TRANSIENT_SMTP_CODES = {421, 450, 451, 452}


@channel(code="email", display_name="Email")
class EmailChannel(ChannelAdapter):
    code:         str        = "email"
    display_name: str        = "Email"
    capabilities: Capability = Capability(
        rich_text=True, subject_line=True, link_button=False,
        attachment=False, max_body_length=100_000
    )

    REQUIRED_SETTINGS = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "sender_name", "sender_email"]

    def validate_settings(self, settings: dict) -> list[str]:
        errors = []
        for key in self.REQUIRED_SETTINGS:
            if not settings.get(key):
                errors.append(f"缺少必要設定：{key}")
        return errors

    def normalize_address(self, raw: str) -> str:
        return raw.strip().lower()

    def classify_failure(self, exc: Exception) -> FailureKind:
        exc_str = str(exc)
        if "535" in exc_str or "Authentication" in exc_str:
            return FailureKind.AUTH_FAILED
        if "550" in exc_str or "5.1.1" in exc_str:
            return FailureKind.PERMANENT_ADDRESS
        if "421" in exc_str or "450" in exc_str:
            return FailureKind.TRANSIENT
        return FailureKind.TRANSIENT

    async def send(self, subject: str | None, body: str, address: str, settings: dict) -> SendResult:
        import aiosmtplib

        # Dry-run 模式（NOTIFY_DRY_RUN=true）
        if notify_config.is_dry_run():
            logger.info("[通知][DRY-RUN] Email 模擬發送至 %s", address)
            return SendResult(ok=True, provider_message_id="dry-run")

        start = time.monotonic()
        try:
            smtp_host = settings.get("smtp_host", "")
            smtp_port = int(settings.get("smtp_port", 587))
            smtp_user = settings.get("smtp_user", "")
            smtp_pass = settings.get("smtp_password", "")
            sender_name  = settings.get("sender_name", "MyStock")
            sender_email = settings.get("sender_email", smtp_user)
            use_tls  = str(settings.get("use_tls", "false")).lower() == "true"
            starttls = str(settings.get("use_starttls", "true")).lower() == "true"

            msg = EmailMessage()
            msg["Subject"] = (notify_config.get_email_subject_prefix() + (subject or "通知")).strip()
            msg["From"]    = f"{sender_name} <{sender_email}>"
            msg["To"]      = address

            # 嘗試 HTML，退回純文字
            if body.strip().startswith("<"):
                msg.set_content("（請使用支援 HTML 的郵件客戶端查閱）")
                msg.add_alternative(body, subtype="html")
            else:
                msg.set_content(body)

            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, use_tls=use_tls)
            await smtp.connect()
            if starttls and not use_tls:
                await smtp.starttls()
            await smtp.login(smtp_user, smtp_pass)
            result = await smtp.sendmail(sender_email, [address], msg.as_string())
            await smtp.quit()

            latency = int((time.monotonic() - start) * 1000)
            logger.info("[通知] Email 發送成功 → %s (%d ms)", address, latency)
            return SendResult(ok=True, latency_ms=latency)

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            kind    = self.classify_failure(exc)
            reason  = str(exc)[:300]
            logger.warning("[通知] Email 發送失敗 → %s [%s] %s", address, kind.value, reason)
            return SendResult(ok=False, failure_kind=kind, failure_reason=reason, latency_ms=latency)

    async def health_check(self, settings: dict) -> HealthResult:
        """連線測試（UC-09）：只驗證 SMTP 連線與認證，不發送任何訊息"""
        import aiosmtplib
        try:
            smtp_host = settings.get("smtp_host", "")
            smtp_port = int(settings.get("smtp_port", 587))
            smtp_user = settings.get("smtp_user", "")
            smtp_pass = settings.get("smtp_password", "")
            use_tls   = str(settings.get("use_tls", "false")).lower() == "true"
            starttls  = str(settings.get("use_starttls", "true")).lower() == "true"

            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port, use_tls=use_tls)
            await smtp.connect()
            if starttls and not use_tls:
                await smtp.starttls()
            await smtp.login(smtp_user, smtp_pass)
            await smtp.quit()
            return HealthResult(ok=True, detail="SMTP 連線與認證成功")
        except Exception as exc:
            return HealthResult(ok=False, detail=str(exc)[:200])
