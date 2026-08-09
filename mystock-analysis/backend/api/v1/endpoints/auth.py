"""超重主管覆核 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
UnitOfWork 由 Dishka DI 容器自動注入並管理生命週期。
"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.weighbridge import OverweightAuthRequest
from backend.schemas.responses import OverweightAuthResponse
from backend.services.auth_service import verify_overweight

router = APIRouter(prefix="/api/auth", tags=["超重授權"], route_class=DishkaRoute)


@router.post("/overweight", response_model=OverweightAuthResponse)
def api_overweight_auth(
    req: OverweightAuthRequest,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """超重主管覆核驗證（UC-001 附屬）。

    當入廠重量超過系統設定上限時，由前端 OverweightAuthDialog 收集
    主管帳號與密碼後呼叫此端點進行驗證。

    Request Body: OverweightAuthRequest
        - userNo:        主管帳號
        - password:      主管密碼
        - ticketWeight:  本次入廠重量（Kg）
        - weightLimit:   系統設定上限（Kg）

    Returns:
        驗證通過：{ status: "authorized", userNo, userName, message }
        驗證失敗：HTTP 403 + { error_code: "AUTH_DENIED", message }

    DB 資料表：user_mstr1（SELECT）
    """
    return verify_overweight(
        uow, req.userNo, req.password,
        req.ticketWeight, req.weightLimit,
        locale,
    )
