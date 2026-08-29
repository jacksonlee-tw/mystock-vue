import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from notify.dispatcher import DispatcherWorker


class NotifyDispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_delivery_writes_delivery_and_activity_logs(self):
        adapter = MagicMock()
        adapter.send = AsyncMock(return_value=SimpleNamespace(
            ok=True,
            provider_message_id="provider-123",
        ))
        repo = MagicMock()
        repo.session = MagicMock()
        repo.get_channel = AsyncMock(return_value={"settings_enc": "encrypted"})
        repo.get_endpoint = AsyncMock(return_value={"address": "recipient-address"})
        repo.mark_sent = AsyncMock()
        repo.log_attempt = AsyncMock()
        repo.reset_channel_failures = AsyncMock()

        activity_repo = MagicMock()
        activity_repo.log = AsyncMock()

        message = {
            "id": 42,
            "endpoint_id": 7,
            "channel_code": "telegram",
            "attempt_count": 0,
            "subject": "subject",
            "body": "body",
        }

        with (
            patch("notify.dispatcher.get_channel", return_value=adapter),
            patch("notify.channel_config.decrypt_settings", return_value={}),
            patch("notify.channel_config.should_circuit_break", return_value=False),
            patch("repositories.activity_log_repository.ActivityLogRepository", return_value=activity_repo),
            patch("notify.dispatcher.time.monotonic", side_effect=[10.0, 10.0]),
        ):
            await DispatcherWorker()._dispatch_one(message, repo)

        repo.mark_sent.assert_awaited_once_with(42, "provider-123")
        repo.log_attempt.assert_awaited_once()
        activity_repo.log.assert_awaited_once_with(
            "NOTIFY_MESSAGE_SENT",
            view_id="notify_dispatcher",
            detail="telegram 通知發送成功：message_id=42, endpoint_id=7",
            success=True,
            rel_id=42,
            comments="provider_message_id=provider-123; latency_ms=0",
            created_by="system",
        )


if __name__ == "__main__":
    unittest.main()