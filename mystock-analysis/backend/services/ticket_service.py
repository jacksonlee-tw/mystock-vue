"""磅單查詢與列印業務邏輯層（UC-003 + 查詢）

此模組負責磅單重印、磅單查詢、當日清單等業務邏輯。
入廠/出廠/採購單/授權等功能已拆分至各自的 Service 模組。
透過 UnitOfWork 存取 Repository，並統一控制交易邊界。
"""
import logging
from datetime import datetime

from backend.core.exceptions import AppException
from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.domain.ports.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


def reprint_ticket(uow: UnitOfWork, ticket_no: str, ticket_type: str,
                   locale: str = DEFAULT_LOCALE) -> dict:
    """UC-003：重印磅單（業務邏輯）。

    磅單號碼為空時拋出 AppException(TICKET_NO_EMPTY, 400)。
    成功訊息透過 translate() 依語系回傳。
    """
    ticket_no = ticket_no.strip()
    if not ticket_no:
        raise AppException("TICKET_NO_EMPTY", status_code=400)

    is_entry = (ticket_type == "in")
    count = uow.tickets.update_print_count(ticket_no, is_entry)
    uow.tickets.add_print_log(ticket_no, ticket_type, found=(count > 0))
    uow.commit()

    msg_key = "PRINT_ENTRY_SUCCESS" if is_entry else "PRINT_EXIT_SUCCESS"
    log.info("[重印] %s磅單=%s 列印次數=%d",
             "入廠" if is_entry else "出廠", ticket_no, count)

    return {
        "status":     "success",
        "message":    translate(msg_key, locale, ticket_no=ticket_no),
        "printCount": count,
    }


def get_ticket(uow: UnitOfWork, ticket_no: str, locale: str = DEFAULT_LOCALE) -> dict:
    """查詢磅單。

    查無磅單時拋出 AppException(TICKET_NOT_FOUND, 404)。
    Repository 回傳的 status（completed/in_progress）以 ticketStatus 回傳，
    避免覆蓋外層的 status="found"。
    """
    result = uow.tickets.get_ticket(ticket_no)
    if not result:
        raise AppException("TICKET_NOT_FOUND", status_code=404, ticket_no=ticket_no)

    ticket_status = result.pop("status", "in_progress")
    return {"status": "found", "ticketStatus": ticket_status, **result}


def list_today_tickets(uow: UnitOfWork) -> dict:
    """當日磅單清單（無需 locale，不回傳訊息文字）。"""
    tickets = uow.tickets.list_today_tickets()
    return {
        "date":    datetime.now().strftime("%Y%m%d"),
        "count":   len(tickets),
        "tickets": tickets,
        "dbMode":  uow.db_mode,
    }


