"""警告日誌 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
UnitOfWork 由 Dishka DI 容器自動注入並管理生命週期。
"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.weighbridge import WarnlogRequest
from backend.schemas.responses import SuccessMessageResponse
from backend.services.warnlog_service import create_warnlog

router = APIRouter(prefix="/api", tags=["警告日誌"], route_class=DishkaRoute)


@router.post("/warnlog", response_model=SuccessMessageResponse)
def api_create_warnlog(
    req: WarnlogRequest,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """寫入採購量警示日誌（UC-005 附屬）。

    前端在偵測到累計進貨量（InQty / MENGE）超過 80%/90%/100% 門檻時呼叫此端點，
    將警示事件記錄至 Warnlog 資料表以備稽核。
    對應 Delphi IsWarningMessage 函式中的 INSERT INTO Warnlog 邏輯。

    Request Body: WarnlogRequest
        - dbNo:        磅單號碼
        - aufnr:       採購單號
        - truckNo:     車號
        - planQty:     採購計劃數量（Kg）
        - loadQty:     本次裝載量（Kg）
        - currentQty:  目前累計進貨量（Kg）
        - log:         警示訊息（例：「採購量已達 90%」）

    Returns:
        { status: "success", message: str }

    DB 資料表：Warnlog（INSERT）
    """
    return create_warnlog(uow, req.model_dump(), locale)
