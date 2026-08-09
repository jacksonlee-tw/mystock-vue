"""入廠過磅 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
UnitOfWork 由 Dishka DI 容器自動注入並管理生命週期。
"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.weighbridge import EntryRecord
from backend.schemas.responses import EntryConfirmResponse
from backend.services.entry_service import confirm_entry

router = APIRouter(prefix="/api/in", tags=["入廠過磅"], route_class=DishkaRoute)


@router.post("/confirm", response_model=EntryConfirmResponse)
def api_confirm_entry(
    record: EntryRecord,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """UC-001：入廠過磅確認"""
    return confirm_entry(uow, record, locale)
