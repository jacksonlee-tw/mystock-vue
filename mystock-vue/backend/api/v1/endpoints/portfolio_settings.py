"""記帳試算參數設定（prototype 追加提案，設計文件原文缺這個章節——見
docs/8.個人投資記帳功能/prototype/index.html 設定頁的說明：§一要求手續費「可設定折讓」，
但設計文件沒有規劃存放這些參數的地方，因此在這裡補上）。單一列，見 V8 migration。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.owner_auth import require_owner
from db.session import get_db
from repositories.portfolio_repository import PortfolioRepository
from services.portfolio_ledger import to_float

router = APIRouter(
    prefix="/api/v1/settings",
    tags=["Portfolio - Settings"],
    dependencies=[Depends(require_owner)],
)


class SettingsUpdate(BaseModel):
    tw_fee_rate: Optional[float] = None
    tw_fee_discount: Optional[float] = None
    tw_fee_min: Optional[float] = None
    tw_tax_rate: Optional[float] = None
    tw_tax_rate_etf: Optional[float] = None
    us_fee_rate: Optional[float] = None
    us_sec_fee_rate: Optional[float] = None
    fx_rate: Optional[float] = None
    cost_method: Optional[str] = None
    dividend_mode: Optional[str] = None
    near_target_pct: Optional[float] = None


def _settings_out(row: dict) -> dict:
    return {k: (to_float(v) if k not in ("cost_method", "dividend_mode", "updated_at") else v) for k, v in row.items() if k != "updated_at"}


@router.get("", summary="取得目前記帳試算參數")
async def get_settings(db=Depends(get_db)):
    row = await PortfolioRepository(db).get_settings()
    return {"success": True, "data": _settings_out(row)}


@router.put("", summary="更新記帳試算參數")
async def update_settings(payload: SettingsUpdate, db=Depends(get_db)):
    if payload.cost_method is not None and payload.cost_method not in ("fifo", "average"):
        raise HTTPException(400, "cost_method 必須為 fifo 或 average")
    if payload.dividend_mode is not None and payload.dividend_mode not in ("income", "reduce_cost"):
        raise HTTPException(400, "dividend_mode 必須為 income 或 reduce_cost")
    for pct_field in ("tw_fee_discount",):
        v = getattr(payload, pct_field)
        if v is not None and not (0 <= v <= 1):
            raise HTTPException(400, f"{pct_field} 必須介於 0～1 之間")
    for positive_field in (
        "tw_fee_rate", "tw_fee_min", "tw_tax_rate", "tw_tax_rate_etf", "us_fee_rate", "us_sec_fee_rate",
        "fx_rate", "near_target_pct",
    ):
        v = getattr(payload, positive_field)
        if v is not None and v < 0:
            raise HTTPException(400, f"{positive_field} 不可為負數")

    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, "沒有提供任何要更新的欄位")

    row = await PortfolioRepository(db).update_settings(patch)
    return {"success": True, "data": _settings_out(row), "message": "設定已更新"}
