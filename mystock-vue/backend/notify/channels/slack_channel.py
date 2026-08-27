"""
notify/channels/slack_channel.py
Slack 管道轉接器（ADR-14：Incoming Webhook，單向 POST，無 bot token/OAuth）
"""
from __future__ import annotations
import logging
import time

from . import channel
from .base import ChannelAdapter, Capability, SendResult, FailureKind, HealthResult
from notify import config as notify_config

logger = logging.getLogger("mystock-backend")

MAX_LEN = 40000  # Slack 單則訊息文字長度上限（留餘裕，官方上限為 40,000 字元）


@channel(code="slack", display_name="Slack")
class SlackChannel(ChannelAdapter):
    code:         str        = "slack"
    display_name: str        = "Slack"
    capabilities: Capability = Capability(
        rich_text=False, subject_line=False, link_button=True,
        attachment=False, max_body_length=MAX_LEN
    )

    REQUIRED_SETTINGS = ["webhook_url"]

    def validate_settings(self, settings: dict) -> list[str]:
        webhook_url = settings.get("webhook_url", "")
        if not webhook_url:
            return ["缺少必要設定：webhook_url"]
        if not webhook_url.startswith("https://hooks.slack.com/"):
            return ["webhook_url 格式不正確，應以 https://hooks.slack.com/ 開頭"]
        return []

    def normalize_address(self, raw: str) -> str:
        """Slack address 是頻道／使用者識別（Incoming Webhook 已綁定固定頻道，通常留空或作標籤用）"""
        return str(raw).strip()

    def classify_failure(self, exc: Exception) -> FailureKind:
        exc_str = str(exc).lower()
        if "invalid_token" in exc_str or "401" in exc_str:
            return FailureKind.AUTH_FAILED
        if "channel_not_found" in exc_str or "404" in exc_str or "no_service" in exc_str:
            return FailureKind.PERMANENT_ADDRESS
        if "channel_is_archived" in exc_str or "403" in exc_str:
            return FailureKind.PERMANENT_BLOCKED
        if "429" in exc_str or "rate" in exc_str:
            return FailureKind.RATE_LIMITED
        return FailureKind.TRANSIENT

    def _truncate(self, text: str) -> str:
        if len(text) <= MAX_LEN:
            return text
        suffix = "\n…（訊息過長已截斷）"
        return text[:MAX_LEN - len(suffix)] + suffix

    async def _post(self, webhook_url: str, text: str) -> tuple[bool, str, int]:
        """共用的 Incoming Webhook POST（含 latency 量測），回傳 (ok, detail, latency_ms)"""
        import httpx

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json={"text": text})
        latency = int((time.monotonic() - start) * 1000)

        body = (resp.text or "").strip()
        if resp.status_code == 200 and body == "ok":
            return True, "ok", latency

        # Slack 錯誤回應是純文字（非 JSON），例如 "invalid_token"、"channel_not_found"
        return False, body or str(resp.status_code), latency

    async def send(self, subject: str | None, body: str, address: str, settings: dict) -> SendResult:
        if notify_config.is_dry_run():
            logger.info("[通知][DRY-RUN] Slack 模擬發送")
            return SendResult(ok=True, provider_message_id="dry-run")

        webhook_url = settings.get("webhook_url", "")
        full_body = f"*{subject}*\n\n{body}" if subject else body
        full_body = self._truncate(full_body)

        try:
            ok, detail, latency = await self._post(webhook_url, full_body)
            if ok:
                logger.info("[通知] Slack 發送成功 (%d ms)", latency)
                return SendResult(ok=True, latency_ms=latency)

            if "rate" in detail.lower() or "429" in detail:
                return SendResult(
                    ok=False, failure_kind=FailureKind.RATE_LIMITED,
                    failure_reason=detail, latency_ms=latency, retry_after_sec=60
                )

            kind = self.classify_failure(Exception(detail))
            logger.warning("[通知] Slack 發送失敗 [%s] %s", kind.value, detail)
            return SendResult(ok=False, failure_kind=kind, failure_reason=detail[:300], latency_ms=latency)

        except Exception as exc:
            kind   = self.classify_failure(exc)
            reason = str(exc)[:300]
            logger.warning("[通知] Slack 發送例外 [%s] %s", kind.value, reason)
            return SendResult(ok=False, failure_kind=kind, failure_reason=reason)

    async def health_check(self, settings: dict) -> HealthResult:
        """
        連線測試：Incoming Webhook 是單向端點，沒有等效於 getMe 的唯讀查詢 API，
        驗證連線的唯一方式是實際 POST 一則低調的測試訊息（非模擬）。
        """
        webhook_url = settings.get("webhook_url", "")
        if not webhook_url:
            return HealthResult(ok=False, detail="webhook_url 未設定")
        try:
            ok, detail, _ = await self._post(webhook_url, "🔔 MyStock 投資系統：連線測試訊息")
            if ok:
                return HealthResult(ok=True, detail="已連接 Slack Webhook，測試訊息已送出")
            return HealthResult(ok=False, detail=detail[:200])
        except Exception as exc:
            return HealthResult(ok=False, detail=str(exc)[:200])
