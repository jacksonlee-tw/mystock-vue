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

    @staticmethod
    def _tls_mode(settings: dict, port: int) -> tuple[bool, bool]:
        """決定 (use_tls, starttls)。

        SMTP 慣例：465 是 implicit TLS（連上即握手），587／25 是 STARTTLS（先明文再升級）。
        對 465 送 STARTTLS 會在升級前就被伺服器切斷，症狀正是 "Unexpected EOF received"，
        所以未明確指定加密方式時一律依埠號推導，不能固定用 STARTTLS。
        """
        security = str(settings.get("smtp_security", "")).strip().lower()
        if security in ("ssl", "tls", "ssl/tls", "implicit", "smtps"):
            return True, False
        if security == "starttls":
            return False, True

        # 舊設定相容：曾明確寫入 use_tls / use_starttls 就照舊值
        if "use_tls" in settings or "use_starttls" in settings:
            use_tls = str(settings.get("use_tls", "false")).lower() == "true"
            starttls = (not use_tls) and str(settings.get("use_starttls", "true")).lower() == "true"
            return use_tls, starttls

        # 未指定 → 依埠號推導
        return (port == 465), (port != 465)

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
            use_tls, starttls = self._tls_mode(settings, smtp_port)

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

            # start_tls 交給 aiosmtplib 在 connect() 內處理：它預設為 None（自動升級），
            # 連線後再手動呼叫 starttls() 會得到 "Connection already using TLS"。
            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port,
                                   use_tls=use_tls, start_tls=starttls)
            await smtp.connect()
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

    async def health_check(self, settings: dict, test_addresses: list[str] | None = None) -> HealthResult:
        """連線測試（UC-09）：只驗證 SMTP 連線與認證，不發送任何訊息
        （test_addresses 不使用：SMTP 連線/認證成功與否已足以判斷可用性，送測試信反而會製造垃圾郵件）"""
        import aiosmtplib
        try:
            smtp_host = settings.get("smtp_host", "")
            smtp_port = int(settings.get("smtp_port", 587))
            smtp_user = settings.get("smtp_user", "")
            smtp_pass = settings.get("smtp_password", "")
            use_tls, starttls = self._tls_mode(settings, smtp_port)

            smtp = aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port,
                                   use_tls=use_tls, start_tls=starttls)
            await smtp.connect()
            await smtp.login(smtp_user, smtp_pass)
            await smtp.quit()
            mode = "SSL/TLS" if use_tls else ("STARTTLS" if starttls else "無加密")
            return HealthResult(ok=True, detail=f"SMTP 連線與認證成功（埠 {smtp_port}／{mode}）")
        except Exception as exc:
            return HealthResult(ok=False, detail=str(exc)[:200])
