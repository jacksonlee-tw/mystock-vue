"""車輛清單查詢 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
使用 UnitOfWork 管理 Repository 存取與交易邊界。
"""
from typing import Optional

from fastapi import APIRouter, Query
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.responses import TruckListResponse
from backend.services.truck_service import list_trucks

router = APIRouter(prefix="/api", tags=["車輛管理"], route_class=DishkaRoute)


@router.get("/trucks", response_model=TruckListResponse)
def api_list_trucks(
    uow: FromDishka[UnitOfWork],
    keyword: Optional[str] = Query(None, description="車號關鍵字過濾"),
):
    """車輛清單查詢（排除黑名單），供前端車號自動完成使用。

    對應 Delphi FillDataTruckList 程序。
    從 CMM_SCALE 取不重複車號，JOIN TruckList 取運輸公司資訊，
    排除 IsBlack=1 的黑名單車輛，依最後磅單號降冪排序。

    Query Params:
        keyword: 車號關鍵字（模糊搜尋），不傳則回傳全部。

    Returns:
        { count: int, trucks: list[{ truckNo, lastProdName, lastDbNo, trancomp }] }

    DB 資料表：CMM_SCALE（SELECT DISTINCT）、TruckList（LEFT JOIN）
    """
    return list_trucks(uow, keyword)
