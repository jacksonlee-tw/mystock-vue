"""追蹤記錄業務邏輯層

負責操作稽核追蹤記錄的商業邏輯。
透過 UnitOfWork 存取 Repository，並統一控制交易邊界。
"""
from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.domain.ports.unit_of_work import UnitOfWork


def create_trace(uow: UnitOfWork, data: dict, locale: str = DEFAULT_LOCALE) -> dict:
    """寫入操作稽核追蹤記錄（業務邏輯層）。

    成功訊息透過 translate() 依語系回傳。
    """
    trace_id = uow.traces.insert_trace(data)
    uow.commit()
    return {
        "status":  "success",
        "message": translate("TRACE_SUCCESS", locale),
        "traceId": trace_id,
    }
