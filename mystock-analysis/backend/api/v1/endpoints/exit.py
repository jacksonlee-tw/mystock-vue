"""出廠過磅 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
UnitOfWork 由 Dishka DI 容器自動注入並管理生命週期。
"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.weighbridge import ExitRecord
from backend.schemas.responses import ExitConfirmResponse
from backend.services.exit_service import confirm_exit

router = APIRouter(prefix="/api/out", tags=["出廠過磅"], route_class=DishkaRoute)


@router.post("/confirm", response_model=ExitConfirmResponse)
def api_confirm_exit(
    record: ExitRecord,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """UC-002：出廠過磅確認"""
    return confirm_exit(uow, record, locale)
