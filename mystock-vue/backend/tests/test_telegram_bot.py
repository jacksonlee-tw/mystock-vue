import unittest
from unittest.mock import AsyncMock, patch

from notify import telegram_bot


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Response:
    status_code = 409


class _Client:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, *args, **kwargs):
        return _Response()


class TelegramPollerTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_channel_does_not_decrypt_settings(self):
        repo = AsyncMock()
        repo.get_channel.return_value = {
            "channel_code": "telegram",
            "status": "disabled",
            "settings_enc": "invalid-old-ciphertext",
        }

        with patch("notify.channel_config.decrypt_settings") as decrypt_settings:
            token = await telegram_bot._get_bot_token(repo)

        self.assertIsNone(token)
        decrypt_settings.assert_not_called()

    async def test_poller_stops_when_another_instance_owns_get_updates(self):
        with (
            patch("db.session.get_async_session", return_value=_SessionContext()),
            patch("repositories.notify_repository.NotifyRepository", return_value=object()),
            patch.object(telegram_bot, "_get_bot_token", AsyncMock(return_value="secret-token")),
            patch("httpx.AsyncClient", _Client),
            self.assertLogs("mystock-backend", level="WARNING") as logs,
        ):
            poller = telegram_bot.TelegramPoller()
            poller._running = True

            await poller._poll_once()

        self.assertFalse(poller._running)
        self.assertIn("同一 bot token 正由另一個實例輪詢", "\n".join(logs.output))
