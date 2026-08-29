"""現金流與股利管理（設計文件 §四）：兩個獨立 router（/dividends、/cashflow），
比照 api/v1/endpoints/notify_admin.py 一個檔案匯出多個 router 的寫法。"""
from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.owner_auth import require_owner
from db.session import get_db
from repositories.portfolio_repository import PortfolioRepository
from services.portfolio_ledger import to_float

dividend_router = APIRouter(
    prefix="/api/v1/dividends",
    tags=["Portfolio - Dividends"],
    dependencies=[Depends(require_owner)],
)
cashflow_router = APIRouter(
    prefix="/api/v1/cashflow",
    tags=["Portfolio - Cashflow"],
    dependencies=[Depends(require_owner)],
)


class DividendIn(BaseModel):
    market: str
    symbol: str
    name: Optional[str] = None
    pay_date: date_cls
    type: str  # cash | stock
    amount: Optional[float] = None
    shares: Optional[float] = None
    note: Optional[str] = None


class CashflowIn(BaseModel):
    flow_date: date_cls
    type: str  # deposit | withdraw
    amount: float
    note: Optional[str] = None


def _dividend_out(row: dict) -> dict:
    return {
        "id": row["id"], "market": row["market"], "symbol": row["symbol"], "name": row["name"],
        "pay_date": row["pay_date"].isoformat(), "type": row["type"],
        "amount": to_float(row["amount"]) if row["amount"] is not None else None,
        "shares": to_float(row["shares"]) if row["shares"] is not None else None,
        "note": row["note"],
    }


def _cashflow_out(row: dict) -> dict:
    return {
        "id": row["id"], "flow_date": row["flow_date"].isoformat(), "type": row["type"],
        "amount": to_float(row["amount"]), "note": row["note"],
    }


# ── 股利紀錄 ─────────────────────────────────────────────────────────────
@dividend_router.get("", summary="查詢股利紀錄")
async def list_dividends(market: Optional[str] = Query(None), db=Depends(get_db)):
    rows = await PortfolioRepository(db).list_dividends(market)
    return {"success": True, "data": [_dividend_out(r) for r in rows]}


@dividend_router.post("", summary="新增股利紀錄")
async def create_dividend(payload: DividendIn, db=Depends(get_db)):
    if payload.market not in ("tw", "us"):
        raise HTTPException(400, "market 必須為 tw 或 us")
    if payload.type not in ("cash", "stock"):
        raise HTTPException(400, "type 必須為 cash 或 stock")
    if payload.type == "cash" and (payload.amount is None or payload.amount < 0):
        raise HTTPException(400, "現金股利需提供金額")
    if payload.type == "stock" and (payload.shares is None or payload.shares < 0):
        raise HTTPException(400, "股票股利需提供股數")

    symbol = payload.symbol.strip().upper()
    row = await PortfolioRepository(db).create_dividend({
        "market": payload.market, "symbol": symbol, "name": (payload.name or symbol).strip(),
        "pay_date": payload.pay_date, "type": payload.type,
        "amount": payload.amount if payload.type == "cash" else None,
        "shares": payload.shares if payload.type == "stock" else None,
        "note": payload.note,
    })
    return {"success": True, "data": _dividend_out(row), "message": "已新增股利紀錄"}


@dividend_router.delete("/{dividend_id}", summary="刪除股利紀錄")
async def delete_dividend(dividend_id: int, db=Depends(get_db)):
    ok = await PortfolioRepository(db).delete_dividend(dividend_id)
    if not ok:
        raise HTTPException(404, "找不到股利紀錄")
    return {"success": True, "message": "已刪除股利紀錄"}


# ── 資金出入金 ───────────────────────────────────────────────────────────
@cashflow_router.get("", summary="查詢資金出入金紀錄")
async def list_cashflows(db=Depends(get_db)):
    rows = await PortfolioRepository(db).list_cashflows()
    return {"success": True, "data": [_cashflow_out(r) for r in rows]}


@cashflow_router.post("", summary="新增資金出入金紀錄")
async def create_cashflow(payload: CashflowIn, db=Depends(get_db)):
    if payload.type not in ("deposit", "withdraw"):
        raise HTTPException(400, "type 必須為 deposit 或 withdraw")
    if payload.amount is None or payload.amount <= 0:
        raise HTTPException(400, "金額必須大於 0")
    row = await PortfolioRepository(db).create_cashflow({
        "flow_date": payload.flow_date, "type": payload.type, "amount": payload.amount, "note": payload.note,
    })
    return {"success": True, "data": _cashflow_out(row), "message": "已新增紀錄"}


@cashflow_router.delete("/{cashflow_id}", summary="刪除資金出入金紀錄")
async def delete_cashflow(cashflow_id: int, db=Depends(get_db)):
    ok = await PortfolioRepository(db).delete_cashflow(cashflow_id)
    if not ok:
        raise HTTPException(404, "找不到出入金紀錄")
    return {"success": True, "message": "已刪除紀錄"}
