"""
notify/telegram_bot.py
Telegram 入站處理（ADR-06：long polling 為預設，TELEGRAM_WEBHOOK_BASE 有設定時才切 webhook；
兩種模式共用同一組 process_update() 處理函式）

負責：
- 消費綁定碼（FR-BD-03/04/05）：使用者在對話 / 群組中送出綁定碼 → 自動建立端點並回覆確認訊息
- /unbind 指令：解除綁定，立即停止發送（FR-BD-06）
"""
from __future__ import annotations
import asyncio
import logging
import re
from typing import Any

from notify import config as notify_config

logger = logging.getLogger("mystock-backend")

_BIND_CODE_RE = re.compile(r"^\d{4}$")


async def _get_bot_token(repo: Any) -> str | None:
    from notify.channel_config import decrypt_settings
    channel_row = await repo.get_channel("telegram")
    if not channel_row:
        return None
    settings = decrypt_settings(channel_row.get("settings_enc") or "")
    return settings.get("bot_token")


async def _reply(bot_token: str, chat_id: Any, text: str) -> None:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
    except Exception as exc:
        logger.warning("[通知] Telegram 回覆訊息失敗（已靜默）：%s", exc)


async def process_update(update: dict, repo: Any) -> None:
    """處理單一 Telegram update（訊息事件）。polling 與 webhook 都呼叫這個函式。"""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat", {})
    chat_id   = chat.get("id")
    chat_type = chat.get("type", "private")
    text      = (message.get("text") or "").strip()
    if chat_id is None or not text:
        return

    bot_token = await _get_bot_token(repo)
    if not bot_token:
        logger.warning("[通知] Telegram bot_token 未設定，忽略入站訊息")
        return

    if text in ("/start",):
        await _reply(bot_token, chat_id, "歡迎使用 MyStock 通知機器人。請貼上系統擁有者提供的 4 位數綁定碼以完成綁定。")
        return

    if text in ("/unbind",):
        await _handle_unbind(chat_id, bot_token, repo)
        return

    if _BIND_CODE_RE.match(text):
        await _handle_bind_code(text, chat_id, chat_type, chat, bot_token, repo)
        return

    # 其他訊息內容：Phase 1/2 不支援雙向互動查詢（需求規格書 §3.2 Q-10，列入 Phase 5），忽略即可


async def _handle_bind_code(code: str, chat_id: Any, chat_type: str, chat: dict, bot_token: str, repo: Any) -> None:
    from notify import binding, recipients

    row = await binding.consume_token(code, "telegram_bind", repo)
    if not row:
        await _reply(bot_token, chat_id, "綁定碼無效或已逾時，請向系統擁有者重新索取。")
        return

    address = str(chat_id)
    is_group = chat_type in ("group", "supergroup")

    try:
        existing = await repo.get_endpoint_by_address("telegram", address)
        if existing:
            await _reply(bot_token, chat_id, "此對話已完成綁定，將持續接收通知。")
            return

        if is_group or row.get("recipient_id") is None:
            note = chat.get("title", "Telegram 群組")
            ep = await recipients.create_shared_endpoint("telegram", address, note, repo)
        else:
            recipient = await repo.get_recipient(row["recipient_id"])
            if not recipient:
                await _reply(bot_token, chat_id, "綁定碼有效，但對應的收件人已不存在，請聯絡系統擁有者。")
                return
            ep = await recipients.create_personal_endpoint(
                recipient["recipient_code"], "telegram", address, repo
            )
            # Telegram 綁定不需要另外驗證（使用者主動在對話中送出綁定碼即已證明可收訊）
            await repo.update_endpoint(ep["id"], {"verify_status": "verified"})

        await _reply(bot_token, chat_id, "綁定成功，將開始接收通知。若要取消，可隨時傳送 /unbind。")
        logger.info("[通知] Telegram 綁定成功 endpoint=%s scope=%s", ep["endpoint_code"], ep["endpoint_scope"])
    except Exception as exc:
        logger.warning("[通知] Telegram 綁定建立端點失敗：%s", exc)
        await _reply(bot_token, chat_id, "綁定過程發生錯誤，請聯絡系統擁有者。")


async def _handle_unbind(chat_id: Any, bot_token: str, repo: Any) -> None:
    ep = await repo.get_endpoint_by_address("telegram", str(chat_id))
    if not ep:
        await _reply(bot_token, chat_id, "目前沒有找到與此對話綁定的通知設定。")
        return
    await repo.update_endpoint(ep["id"], {"status": "disabled"})
    await _reply(bot_token, chat_id, "已解除綁定，將立即停止發送通知。")
    logger.info("[通知] Telegram 端點已解除綁定 endpoint=%s", ep["endpoint_code"])


# ── Long polling 常駐迴圈（ADR-06）───────────────────────────
class TelegramPoller:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._offset = 0

    def start(self) -> None:
        if notify_config.get_telegram_webhook_base():
            logger.info("[通知] TELEGRAM_WEBHOOK_BASE 已設定，跳過 long polling（改用 webhook 端點）")
            return
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="notify-telegram-poller")
        logger.info("[通知] Telegram long polling 啟動")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[通知] Telegram long polling 已停止")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[通知] Telegram polling 例外（已靜默，5 秒後重試）：%s", exc)
                await asyncio.sleep(5)

    async def _poll_once(self) -> None:
        import httpx
        from db.session import get_async_session
        from repositories.notify_repository import NotifyRepository

        async with get_async_session() as session:
            repo = NotifyRepository(session)
            bot_token = await _get_bot_token(repo)
            if not bot_token:
                await asyncio.sleep(30)  # 尚未設定機器人憑證，降低輪詢頻率
                return

            async with httpx.AsyncClient(timeout=35) as client:
                resp = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getUpdates",
                    params={"offset": self._offset, "timeout": 30, "allowed_updates": '["message"]'},
                )
            if resp.status_code == 409:
                self._running = False
                logger.warning(
                    "[通知] Telegram long polling 已停止：同一 bot token 正由另一個實例輪詢"
                )
                return
            data = resp.json()
            if not data.get("ok"):
                await asyncio.sleep(5)
                return

            for update in data.get("result", []):
                self._offset = max(self._offset, update.get("update_id", 0) + 1)
                await process_update(update, repo)
            await session.commit()


_poller: TelegramPoller | None = None


def get_poller() -> TelegramPoller:
    global _poller
    if _poller is None:
        _poller = TelegramPoller()
    return _poller


async def start() -> None:
    if not notify_config.is_enabled():
        return
    get_poller().start()


async def stop() -> None:
    if _poller is not None:
        await _poller.stop()
