"""超重主管覆核 Service 單元測試

使用 MemoryUnitOfWork — Mock 帳號 admin/1234。
"""
import pytest

from backend.core.exceptions import AppException
from backend.services.auth_service import verify_overweight


class TestVerifyOverweight:

    def test_valid_admin_authorized(self, uow):
        result = verify_overweight(uow, "admin", "1234", 6000, 5000, "zh-TW")

        assert result["status"] == "authorized"
        assert result["userNo"] == "admin"
        assert result["userName"] == "管理員"

    def test_wrong_password_denied(self, uow):
        with pytest.raises(AppException) as exc_info:
            verify_overweight(uow, "admin", "wrong", 6000, 5000, "zh-TW")
        assert exc_info.value.error_code == "AUTH_DENIED"
        assert exc_info.value.status_code == 403

    def test_nonexistent_user_denied(self, uow):
        with pytest.raises(AppException) as exc_info:
            verify_overweight(uow, "nobody", "1234", 6000, 5000, "zh-TW")
        assert exc_info.value.error_code == "AUTH_DENIED"
