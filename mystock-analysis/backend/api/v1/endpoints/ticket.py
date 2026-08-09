"""磅單查詢與列印 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
UnitOfWork 由 Dishka DI 容器自動注入並管理生命週期。
"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.weighbridge import PrintRequest
from backend.schemas.responses import (
    ReprintResponse,
    TicketDetailResponse,
    TodayTicketsResponse,
)
from backend.services.ticket_service import (
    reprint_ticket,
    get_ticket,
    list_today_tickets,
)

router = APIRouter(prefix="/api", tags=["磅單管理"], route_class=DishkaRoute)


@router.post("/print", response_model=ReprintResponse)
def api_reprint_ticket(
    data: PrintRequest,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """UC-003：重印磅單"""
    return reprint_ticket(uow, data.ticketNo, data.type, locale)


@router.get("/ticket/{ticket_no}", response_model=TicketDetailResponse)
def api_get_ticket(
    ticket_no: str,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """查詢磅單（依磅單號查詢，返回入/出廠資料）"""
    return get_ticket(uow, ticket_no, locale)


@router.get("/tickets/today", response_model=TodayTicketsResponse)
def api_list_today_tickets(uow: FromDishka[UnitOfWork]):
    """當日磅單清單"""
    return list_today_tickets(uow)
