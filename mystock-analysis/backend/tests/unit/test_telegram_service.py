"""Telegram 股票警示通知 Service 單元測試

使用 unittest.mock 模擬 httpx.AsyncClient，零網路依賴。
測試案例涵蓋：正常發送、未設定 Token、逾時、連線失敗、API 回傳錯誤。
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.exceptions import AppException
from backend.services.telegram_service import send_telegram_alert

# ── 測試輔助 ─────────────────────────────────────────────────────────────

FAKE_TOKEN = "1234567890:AABBCCDDEEFF"
FAKE_CHAT_ID = "9876543210"


def _run(coro):
    """在同步測試函式中執行 async coroutine。"""
    return asyncio.run(coro)


def _make_mock_client(response_json: dict) -> AsyncMock:
    """建立 httpx.AsyncClient mock，回傳指定 JSON。"""
    mock_response = MagicMock()
    mock_response.json.return_value = response_json

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ── 測試類別 ─────────────────────────────────────────────────────────────

class TestSendTelegramAlert:

    # ── 正常情境 ──────────────────────────────────────────────────────────

    def test_send_success_returns_message_id(self):
        """正常發送：回傳 status=success 且包含 telegram_msg_id。"""
        mock_client = _make_mock_client({
            "ok": True,
            "result": {"message_id": 42},
        })

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = _run(
                send_telegram_alert(
                    "<b>股票警示</b>\n2330 台積電 已達設定價位！",
                    bot_token=FAKE_TOKEN,
                    chat_id=FAKE_CHAT_ID,
                )
            )

        assert result["status"] == "success"
        assert result["telegram_msg_id"] == 42
        assert "message" in result

    def test_send_success_with_markdown(self):
        """以 Markdown 模式發送。"""
        mock_client = _make_mock_client({
            "ok": True,
            "result": {"message_id": 99},
        })

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = _run(
                send_telegram_alert(
                    "*警示*",
                    parse_mode="Markdown",
                    bot_token=FAKE_TOKEN,
                    chat_id=FAKE_CHAT_ID,
                )
            )

        assert result["status"] == "success"
        assert result["telegram_msg_id"] == 99

    def test_send_success_locale_zh_cn(self):
        """zh-CN 語系回傳簡體中文訊息。"""
        mock_client = _make_mock_client({"ok": True, "result": {"message_id": 1}})

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = _run(
                send_telegram_alert(
                    "test",
                    bot_token=FAKE_TOKEN,
                    chat_id=FAKE_CHAT_ID,
                    locale="zh-CN",
                )
            )

        assert result["status"] == "success"
        # 簡體中文訊息應包含「发送成功」
        assert "成功" in result["message"]

    # ── 設定缺失 ──────────────────────────────────────────────────────────

    def test_missing_bot_token_raises_503(self):
        """未設定 Bot Token → TELEGRAM_NOT_CONFIGURED (503)。"""
        with pytest.raises(AppException) as exc_info:
            _run(send_telegram_alert("msg", bot_token="", chat_id=FAKE_CHAT_ID))

        assert exc_info.value.error_code == "TELEGRAM_NOT_CONFIGURED"
        assert exc_info.value.status_code == 503

    def test_missing_chat_id_raises_503(self):
        """未設定 Chat ID → TELEGRAM_NOT_CONFIGURED (503)。"""
        with pytest.raises(AppException) as exc_info:
            _run(send_telegram_alert("msg", bot_token=FAKE_TOKEN, chat_id=""))

        assert exc_info.value.error_code == "TELEGRAM_NOT_CONFIGURED"
        assert exc_info.value.status_code == 503

    def test_both_missing_raises_503(self):
        """Token 和 Chat ID 都未設定 → TELEGRAM_NOT_CONFIGURED (503)。"""
        with pytest.raises(AppException) as exc_info:
            _run(send_telegram_alert("msg", bot_token="", chat_id=""))

        assert exc_info.value.error_code == "TELEGRAM_NOT_CONFIGURED"

    # ── 網路錯誤 ──────────────────────────────────────────────────────────

    def test_timeout_raises_504(self):
        """httpx 逾時 → TELEGRAM_TIMEOUT (504)。"""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AppException) as exc_info:
                _run(send_telegram_alert("msg", bot_token=FAKE_TOKEN, chat_id=FAKE_CHAT_ID))

        assert exc_info.value.error_code == "TELEGRAM_TIMEOUT"
        assert exc_info.value.status_code == 504

    def test_request_error_raises_502(self):
        """httpx 連線失敗 → TELEGRAM_REQUEST_FAILED (502)。"""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AppException) as exc_info:
                _run(send_telegram_alert("msg", bot_token=FAKE_TOKEN, chat_id=FAKE_CHAT_ID))

        assert exc_info.value.error_code == "TELEGRAM_REQUEST_FAILED"
        assert exc_info.value.status_code == 502

    # ── Telegram API 錯誤 ─────────────────────────────────────────────────

    def test_api_returns_ok_false_raises_502(self):
        """Telegram API 回傳 ok=False → TELEGRAM_SEND_FAILED (502)。"""
        mock_client = _make_mock_client({
            "ok": False,
            "description": "Bad Request: chat not found",
        })

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AppException) as exc_info:
                _run(send_telegram_alert("msg", bot_token=FAKE_TOKEN, chat_id=FAKE_CHAT_ID))

        assert exc_info.value.error_code == "TELEGRAM_SEND_FAILED"
        assert exc_info.value.status_code == 502

    def test_api_returns_no_result_message_id(self):
        """Telegram API 回傳 result 無 message_id → telegram_msg_id 為 None。"""
        mock_client = _make_mock_client({"ok": True, "result": {}})

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = _run(
                send_telegram_alert("msg", bot_token=FAKE_TOKEN, chat_id=FAKE_CHAT_ID)
            )

        assert result["status"] == "success"
        assert result["telegram_msg_id"] is None
