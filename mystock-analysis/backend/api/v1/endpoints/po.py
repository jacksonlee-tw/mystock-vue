"""採購單查詢 API 路由（Controller 層）"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.responses import PoInfoResponse
from backend.services.po_service import get_po

router = APIRouter(prefix="/api", tags=["採購單查詢"], route_class=DishkaRoute)


@router.get("/po/{po_no}", response_model=PoInfoResponse)
def api_get_po(
    po_no: str,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """查詢採購單資料（MM_POWO_SCALE 或 Mock）"""
    return get_po(uow, po_no, locale)
