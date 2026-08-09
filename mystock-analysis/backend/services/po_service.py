"""採購單業務邏輯層（UC-005）

負責採購單查詢的商業邏輯。
透過 UnitOfWork 存取 Repository。
"""
import logging

from backend.core.exceptions import AppException
from backend.core.i18n import DEFAULT_LOCALE
from backend.domain.ports.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


def get_po(uow: UnitOfWork, po_no: str, locale: str = DEFAULT_LOCALE) -> dict:
    """查詢採購單資料（UC-005）。

    查無採購單時拋出 AppException(PO_NOT_FOUND, 404)。
    """
    info = uow.po.get_po_info(po_no)
    if not info:
        raise AppException("PO_NOT_FOUND", status_code=404, po_no=po_no)
    return {"status": "found", **info}
