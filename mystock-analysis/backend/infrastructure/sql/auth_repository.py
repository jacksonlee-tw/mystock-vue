"""超重主管覆核 SQL Repository 實作"""
import logging
from typing import Optional

from backend.domain.ports.auth_repository import AuthRepository
from backend.infrastructure.memory.auth_repository import MemoryAuthRepository

log = logging.getLogger(__name__)


class SqlAuthRepository(AuthRepository):
    """超重主管覆核 SQL Repository — pyodbc MS SQL Server"""

    def __init__(self, conn):
        self._conn = conn
        self._fallback = MemoryAuthRepository()

    def verify_overweight_auth(self, user_no: str, password: str) -> Optional[dict]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT userNo, ISNULL(name, N''),  ISNULL(userkind, N'')
                FROM   user_mstr1
                WHERE  userNo = ? AND password = ?
                """,
                user_no, password,
            )
            row = cur.fetchone()
            if row:
                return {"userNo": row[0], "userName": row[1], "userKind": row[2]}
        except Exception as exc:
            log.warning("verify_overweight_auth DB 失敗：%s", exc)
            return self._fallback.verify_overweight_auth(user_no, password)
        return None
