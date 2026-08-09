"""讀卡機 Service 單元測試

使用 MockCardReaderDriver，零硬體依賴。
"""
import pytest

from backend.devices.drivers.mock_card_reader_driver import MockCardReaderDriver
from backend.devices.services.card_reader_service import read_card_no
from backend.core.exceptions import AppException


@pytest.fixture
def reader():
    """獨立的 MockCardReaderDriver 實例"""
    return MockCardReaderDriver()


class TestReadCardNo:
    """read_card_no Service 測試"""

    def test_read_card_success(self, reader):
        """有卡時應成功回傳卡號"""
        result = read_card_no(reader)
        assert result["status"] == "success"
        assert result["cardNo"] == "A1B2C3D4"
        assert "A1B2C3D4" in result["message"]

    def test_read_card_custom_snr(self, reader):
        """注入自訂卡號後應回傳該卡號"""
        reader.inject_card("DEADBEEF")
        result = read_card_no(reader)
        assert result["cardNo"] == "DEADBEEF"

    def test_read_card_no_card(self, reader):
        """無卡時應拋出 CARD_NOT_DETECTED"""
        reader.remove_card()
        with pytest.raises(AppException) as exc_info:
            read_card_no(reader)
        assert exc_info.value.error_code == "CARD_NOT_DETECTED"
        assert exc_info.value.status_code == 404

    def test_read_card_with_locale(self, reader):
        """指定 locale 應正常回傳"""
        result = read_card_no(reader, locale="zh-CN")
        assert result["status"] == "success"
        assert result["cardNo"] == "A1B2C3D4"
