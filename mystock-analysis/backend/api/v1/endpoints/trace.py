"""追蹤記錄 API 路由（Controller 層）

此路由只負責接收 Request、呼叫 Service 層，以及回傳 Response。
UnitOfWork 由 Dishka DI 容器自動注入並管理生命週期。
"""
from fastapi import APIRouter, Depends
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.domain.ports.unit_of_work import UnitOfWork
from backend.schemas.weighbridge import TraceRequest
from backend.schemas.responses import TraceResponse
from backend.services.trace_service import create_trace

router = APIRouter(prefix="/api", tags=["追蹤記錄"], route_class=DishkaRoute)


@router.post("/trace", response_model=TraceResponse)
def api_create_trace(
    req: TraceRequest,
    uow: FromDishka[UnitOfWork],
    locale: str = Depends(get_locale),
):
    """寫入操作稽核追蹤記錄至 trace_mstr 資料表。

    每次完成入廠（A1）或出廠（B1）作業後，前端呼叫此端點留下操作軌跡，
    供後續稽核與異常追蹤使用。
    對應 Delphi ushare.pas 中的 insertIntotrace_mstr 程序。

    Request Body: TraceRequest
        - dbNo:       磅單號碼（必填）
        - version:    磅單版本號
        - poNo:       採購單號
        - eventName:  事件名稱（例：「入廠過磅(A1)」）
        - truckNo:    車號
        - supply:     供應商名稱
        - prodName:   原料名稱
        - a1Wt ~ b1Wt: 各磅點重量字串
        - userNo:     操作員帳號
        - workFlow:   工作流程代碼（1/2/3）

    Returns:
        { status: "success", message: str, traceId: str }
        traceId 為新產生的 12 碼追蹤記錄 ID（YYYYMMDDNNNN）。

    DB 資料表：trace_mstr（INSERT）
    """
    return create_trace(uow, req.model_dump(), locale)
