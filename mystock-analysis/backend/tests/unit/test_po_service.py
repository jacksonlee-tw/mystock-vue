"""採購單 Service 單元測試（UC-005）

使用 MemoryUnitOfWork — Mock PO 資料（PO001~PO004）。
"""
import pytest

from backend.core.exceptions import AppException
from backend.services.po_service import get_po


class TestGetPo:
    """UC-005：採購單查詢"""

    def test_po001_found(self, uow):
        result = get_po(uow, "PO001", "zh-TW")

        assert result["status"] == "found"
        assert result["materialName"] == "砂石料"
        assert result["supplier"] == "台灣砂石有限公司"
        assert result["planQty"] == 50000.0

    def test_po_not_found_raises(self, uow):
        with pytest.raises(AppException) as exc_info:
            get_po(uow, "PO_NONEXIST", "zh-TW")
        assert exc_info.value.error_code == "PO_NOT_FOUND"
        assert exc_info.value.status_code == 404

    def test_po_ratio_calculated(self, uow):
        result = get_po(uow, "PO002", "zh-TW")

        expected_ratio = 88000.0 / 100000.0  # 0.88
        assert abs(result["ratio"] - expected_ratio) < 0.001
