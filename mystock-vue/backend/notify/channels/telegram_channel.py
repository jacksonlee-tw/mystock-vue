"""
notify/channels/telegram_channel.py
Telegram 管道轉接器（ADR-05：httpx 直呼 Bot API，ADR-06：long polling / webhook 共用）
"""
from __future__ import annotations
import logging
import re
import time

from . import channel
from .base import ChannelAdapter, Capability, SendResult, FailureKind, HealthResult
from notify import config as notify_config

logger = logging.getLogger("mystock-backend")

TG_API_BASE = "https://api.telegram.org/bot{token}"
MAX_LEN     = 4096  # Telegram 單則訊息長度上限


@channel(code="telegram", display_name="Telegram")
class TelegramChannel(ChannelAdapter):
    code:         str        = "telegram"
    display_name: str        = "Telegram"
    capabilities: Capability = Capability(
        rich_text=False, subject_line=False, link_button=True,
        attachment=False, max_body_length=MAX_LEN
    )

    REQUIRED_SETTINGS = ["bot_token"]

    def validate_settings(self, settings: dict) -> list[str]:
        if not settings.get("bot_token"):
            return ["缺少必要設定：bot_token"]
        return []

    def normalize_address(self, raw: str) -> str:
        """Telegram address 是 chat_id，可能是數字或字串，統一為字串"""
        return str(raw).strip()

    def classify_failure(self, exc: Exception) -> FailureKind:
        exc_str = str(exc).lower()
        if "401" in exc_str or "unauthorized" in exc_str:
            return FailureKind.AUTH_FAILED
        if "chat not found" in exc_str or "400" in exc_str:
            return FailureKind.PERMANENT_ADDRESS
        if "bot was blocked" in exc_str or "forbidden" in exc_str:
            return FailureKind.PERMANENT_BLOCKED
        if "429" in exc_str or "too many requests" in exc_str:
            return FailureKind.RATE_LIMITED
        return FailureKind.TRANSIENT

    def _truncate(self, text: str) -> str:
        """超長截斷，保留最後一行的 manage_url（FR-MC-06）"""
        if len(text) <= MAX_LEN:
            return text
        suffix = "\n…（訊息過長已截斷）"
        return text[:MAX_LEN - len(suffix)] + suffix

    def _escape_markdown(self, text: str) -> str:
        """Telegram MarkdownV2 逸脫（特殊字元加反斜線）"""
        special = r"\_*[]()~`>#+-=|{}.!"
        return re.sub(r"([" + re.escape(special) + r"])", r"\\\1", text)

    async def send(self, subject: str | None, body: str, address: str, settings: dict) -> SendResult:
        import httpx

        if notify_config.is_dry_run():
            logger.info("[通知][DRY-RUN] Telegram 模擬發送至 chat_id=%s", address)
            return SendResult(ok=True, provider_message_id="dry-run")

        start     = time.monotonic()
        bot_token = settings.get("bot_token", "")
        url       = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        # 組合標題與內文（Telegram 無 subject，首行作為標題）
        if subject:
            full_body = f"*{subject}*\n\n{body}"
        else:
            full_body = body
        full_body = self._truncate(full_body)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json={
                    "chat_id":    address,
                    "text":       full_body,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                })

            latency = int((time.monotonic() - start) * 1000)
            data    = resp.json()

            if resp.status_code == 200 and data.get("ok"):
                msg_id = str(data.get("result", {}).get("message_id", ""))
                logger.info("[通知] Telegram 發送成功 → chat_id=%s (%d ms)", address, latency)
                return SendResult(ok=True, provider_message_id=msg_id, latency_ms=latency)

            # 處理速率限制（429）
            if resp.status_code == 429:
                retry_after = int(data.get("parameters", {}).get("retry_after", 60))
                reason = f"Too many requests. Retry after {retry_after}s"
                return SendResult(
                    ok=False, failure_kind=FailureKind.RATE_LIMITED,
                    failure_reason=reason, latency_ms=latency, retry_after_sec=retry_after
                )

            # 其他錯誤
            description = data.get("description", str(resp.status_code))[:300]
            kind = self.classify_failure(Exception(f"{resp.status_code} {description}"))
            logger.warning("[通知] Telegram 發送失敗 → %s [%s] %s", address, kind.value, description)
            return SendResult(ok=False, failure_kind=kind, failure_reason=description, latency_ms=latency)

        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            kind    = self.classify_failure(exc)
            reason  = str(exc)[:300]
            logger.warning("[通知] Telegram 發送例外 → %s [%s] %s", address, kind.value, reason)
            return SendResult(ok=False, failure_kind=kind, failure_reason=reason, latency_ms=latency)

    async def health_check(self, settings: dict) -> HealthResult:
        """連線測試：呼叫 getMe API"""
        import httpx
        bot_token = settings.get("bot_token", "")
        if not bot_token:
            return HealthResult(ok=False, detail="bot_token 未設定")
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            data = resp.json()
            if data.get("ok"):
                bot_name = data.get("result", {}).get("username", "")
                return HealthResult(ok=True, detail=f"已連接機器人：@{bot_name}")
            return HealthResult(ok=False, detail=data.get("description", "未知錯誤")[:200])
        except Exception as exc:
            return HealthResult(ok=False, detail=str(exc)[:200])
