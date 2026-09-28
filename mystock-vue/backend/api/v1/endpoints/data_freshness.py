"""登入首頁自動補抓 API（見 docs/19.登入自動補抓資料/登入自動補抓資料_規劃書.md §3.5）。

兩支端點皆掛 `require_owner`——報告內含追蹤清單代號，追蹤清單本身是擁有者資料。
回應信封沿用專案慣例：`{"success": bool, "data": ...}`。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from config import get_enabled_markets
from core.owner_auth import require_owner
from services.freshness_service import build_market_report, catch_up

router = APIRouter(
    prefix="/api/v1/data-freshness", tags=["DataFreshness"], dependencies=[Depends(require_owner)],
)


class CatchUpRequest(BaseModel):
    markets: Optional[List[str]] = None
    force: bool = False


@router.get("", summary="讀取各市場資料新鮮度報告（只讀，不觸發任何抓取）")
async def get_report(market: Optional[str] = None):
    markets = [market] if market else get_enabled_markets()
    data = {m: await build_market_report(m) for m in markets}
    return {"success": True, "data": data}


@router.post("/catch-up", summary="檢查新鮮度並視情況觸發背景補抓（§3.4）")
async def trigger_catch_up(req: CatchUpRequest):
    data = await catch_up(req.markets, force=req.force)
    return {"success": True, "data": data}
