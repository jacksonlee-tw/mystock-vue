"""超重主管覆核記憶體 Repository 實作"""
from typing import Optional

from backend.domain.ports.auth_repository import AuthRepository

# ── Mock 主管帳號 ────────────────────────────────────────────────────────
_MOCK_USERS: dict[str, dict] = {
    "admin": {"password": "1234", "name": "管理員", "userkind": "A"},
}


class MemoryAuthRepository(AuthRepository):
    """超重主管覆核記憶體 Repository"""

    def verify_overweight_auth(self, user_no: str, password: str) -> Optional[dict]:
        user = _MOCK_USERS.get(user_no)
        if user and user["password"] == password:
            return {"userNo": user_no, "userName": user["name"]}
        return None
