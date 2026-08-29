import unittest
from unittest.mock import patch

from notify.channel_config import decrypt_settings


class NotifyChannelConfigTests(unittest.TestCase):
    def test_missing_secret_key_is_logged(self):
        with (
            patch("notify.channel_config.notify_config.get_secret_key", return_value=""),
            self.assertLogs("mystock-backend", level="ERROR") as logs,
        ):
            settings = decrypt_settings("encrypted-settings")

        self.assertEqual({}, settings)
        self.assertIn(
            "[通知] NOTIFY_SECRET_KEY 未設定，無法解密管道設定",
            "\n".join(logs.output),
        )