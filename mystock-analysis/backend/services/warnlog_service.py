"""警告日誌業務邏輯層

負責採購量警示日誌的商業邏輯。
透過 UnitOfWork 存取 Repository，並統一控制交易邊界。
"""
from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.domain.ports.unit_of_work import UnitOfWork


def create_warnlog(uow: UnitOfWork, data: dict, locale: str = DEFAULT_LOCALE) -> dict:
    """寫入採購量警示日誌（業務邏輯層）。

    成功訊息透過 translate() 依語系回傳。
    """
    uow.warnlog.insert_warnlog(data)
    uow.commit()
    return {
        "status":  "success",
        "message": translate("WARNLOG_SUCCESS", locale),
    }
