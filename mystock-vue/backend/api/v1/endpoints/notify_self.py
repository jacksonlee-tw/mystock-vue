"""
api/v1/endpoints/notify_self.py
整合訊息通知平台 — 收件人自助端 API（§6.2 ②，M13）

授權方式：Cookie（require_self_service），與管理端的 require_owner 完全獨立
（不同 Cookie 名稱、不同簽章 salt，§12.1「入口完全分離」）。
所有操作都以 Cookie 解出的 recipient_id 為界，任何跨收件人存取一律視為資源不存在（AC-21）。
"""
from __future__ import annotations
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from db.session import get_db
from repositories.notify_repository import NotifyRepository
from notify.security import require_self_service, NotifyValidationException

router = APIRouter(prefix="/api/v1/notify/me", tags=["Notify Self-Service"])


def envelope(data: Any = None, message: str | None = None) -> dict:
    body = {"success": True, "data": data}
    if message:
        body["message"] = message
    return body


@router.get("", summary="本人資料：端點清單、目前偏好、授權上限（FR-SS-02/03/11）")
async def get_me(recipient_id: int = Depends(require_self_service), db=Depends(get_db)):
    from notify import selfservice
    repo = NotifyRepository(db)
    return envelope(await selfservice.get_my_view(recipient_id, repo))


class PreferenceUpdateRequest(BaseModel):
    markets: Optional[list[str]] = None
    strengths: Optional[list[str]] = None
    signal_types: Optional[list[str]] = None
    strategy_categories: Optional[list[str]] = None
    watch_symbols: Optional[list[str]] = None


@router.patch("/preferences", summary="調整訂閱範圍（只能收窄，FR-SS-04/08，AC-22/24）")
async def update_preferences(
    req: PreferenceUpdateRequest,
    recipient_id: int = Depends(require_self_service),
    db=Depends(get_db),
):
    from notify import selfservice
    repo = NotifyRepository(db)
    updates = req.model_dump(exclude_none=True)
    result = await selfservice.narrow_preferences(recipient_id, updates, repo)
    return envelope(result, "設定已儲存，下次發送即套用")


class EndpointPrefRequest(BaseModel):
    delivery_mode: Optional[str] = None
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None
    daily_limit: Optional[int] = None


@router.patch("/endpoints/{endpoint_code}", summary="調整單一端點的接收節奏（FR-SS-05）")
async def update_my_endpoint_ep(
    endpoint_code: str,
    req: EndpointPrefRequest,
    recipient_id: int = Depends(require_self_service),
    db=Depends(get_db),
):
    from notify import selfservice
    repo = NotifyRepository(db)
    updates = req.model_dump(exclude_none=True)
    result = await selfservice.update_my_endpoint(recipient_id, endpoint_code, updates, repo)
    return envelope(result, "已更新")


class PauseRequest(BaseModel):
    days: int


@router.post("/pause", summary="暫停通知（1/3/7/30 天，到期自動恢復，FR-SS-06）")
async def pause_ep(req: PauseRequest, recipient_id: int = Depends(require_self_service), db=Depends(get_db)):
    from notify import selfservice
    repo = NotifyRepository(db)
    result = await selfservice.pause(recipient_id, req.days, repo)
    return envelope(result, f"已暫停 {req.days} 天，期間不發送、不補送，到期自動恢復")


@router.delete("/pause", summary="提前恢復")
async def resume_ep(recipient_id: int = Depends(require_self_service), db=Depends(get_db)):
    from notify import selfservice
    repo = NotifyRepository(db)
    await selfservice.resume(recipient_id, repo)
    return envelope(None, "已恢復接收通知")


class UnsubscribeRequest(BaseModel):
    scope: str  # "endpoint" | "all"
    endpoint_code: Optional[str] = None
    confirm: bool = False


@router.post("/unsubscribe", summary="退訂單一端點或全部（破壞性操作須 confirm=true，FR-SS-07，AC-17）")
async def unsubscribe_ep(
    req: UnsubscribeRequest,
    recipient_id: int = Depends(require_self_service),
    db=Depends(get_db),
):
    from notify import selfservice
    if not req.confirm:
        raise NotifyValidationException("退訂為不可逆操作，請於請求中帶入 confirm=true 二次確認")
    repo = NotifyRepository(db)
    result = await selfservice.unsubscribe(recipient_id, req.scope, req.endpoint_code, repo)
    return envelope(result, "已退訂，立即生效")


@router.get("/messages", summary="我近 7 天收到的通知（FR-SS-09）")
async def my_messages_ep(recipient_id: int = Depends(require_self_service), db=Depends(get_db)):
    from notify import selfservice
    repo = NotifyRepository(db)
    return envelope(await selfservice.my_recent_messages(recipient_id, repo))
