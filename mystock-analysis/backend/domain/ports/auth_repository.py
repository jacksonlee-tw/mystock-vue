"""超重主管覆核 Repository 介面（Port）"""
from abc import ABC, abstractmethod
from typing import Optional


class AuthRepository(ABC):
    """超重主管覆核 Repository 抽象介面"""

    @abstractmethod
    def verify_overweight_auth(self, user_no: str, password: str) -> Optional[dict]:
        """驗證超重主管帳號密碼

        Returns:
            驗證通過：dict { userNo, userName, userKind }。
            驗證失敗：None。
        """
        ...
