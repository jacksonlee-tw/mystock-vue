"""超重主管覆核業務邏輯層

負責超重授權驗證的商業邏輯。
透過 UnitOfWork 存取 Repository。
"""
import logging

from backend.core.exceptions import AppException
from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.domain.ports.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


def verify_overweight(uow: UnitOfWork, user_no: str, password: str,
                      ticket_weight: float, weight_limit: float,
                      locale: str = DEFAULT_LOCALE) -> dict:
    """UC-001 附屬：超重主管覆核驗證。

    驗證失敗時拋出 AppException(AUTH_DENIED, 403)。
    成功訊息透過 translate() 依語系回傳。
    """
    user = uow.auth.verify_overweight_auth(user_no, password)
    if not user:
        raise AppException("AUTH_DENIED", status_code=403)

    log.info("[超重覆核] 主管=%s(%s) 重量=%s 上限=%s",
             user_no, user.get("userName"), ticket_weight, weight_limit)

    return {
        "status":   "authorized",
        "userNo":   user["userNo"],
        "userName": user.get("userName", ""),
        "message":  translate("AUTH_AUTHORIZED", locale),
    }
