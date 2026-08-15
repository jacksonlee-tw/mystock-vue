"""潛力股觀察名單（設計文件 §五）。到價推播串接 notify 平台留待後續（本次僅頁面顯示距目標價）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from db.session import get_db
from repositories.portfolio_repository import PortfolioRepository
from services.portfolio_ledger import D, Settings, to_float

router = APIRouter(prefix="/api/v1/watchlist", tags=["Portfolio - Watchlist"])


class WatchlistIn(BaseModel):
    market: str
    symbol: str
    name: Optional[str] = None
    target_price: float
    note: Optional[str] = None


class WatchlistUpdate(BaseModel):
    target_price: Optional[float] = None
    note: Optional[str] = None
    name: Optional[str] = None


async def _quotes_for(rows: list[dict]) -> dict[tuple[str, str], float]:
    from api.v1.endpoints.portfolio import _fetch_quotes  # 重用既有批次報價邏輯，不重複實作

    pairs = [(r["market"], r["symbol"]) for r in rows]
    quotes = await _fetch_quotes(pairs)
    return {k: to_float(v) for k, v in quotes.items()}


def _watch_out(row: dict, price: Optional[float], near_target_pct: float) -> dict:
    gap_pct = ((price / to_float(row["target_price"]) - 1) * 100) if price is not None else None
    return {
        "id": row["id"], "market": row["market"], "symbol": row["symbol"], "name": row["name"],
        "added_date": row["added_date"].isoformat(), "target_price": to_float(row["target_price"]),
        "note": row["note"], "price": price, "gap_pct": gap_pct,
        "is_near_target": (gap_pct is not None and abs(gap_pct) <= near_target_pct),
        "is_reached": (gap_pct is not None and gap_pct <= 0),
    }


@router.get("", summary="查詢觀察名單（含目前股價與距目標價）")
async def list_watchlist(market: Optional[str] = Query(None), db=Depends(get_db)):
    repo = PortfolioRepository(db)
    rows = await repo.list_watchlist(market)
    settings = Settings.from_row(await repo.get_settings())
    quotes = await _quotes_for(rows)
    data = [_watch_out(r, quotes.get((r["market"], r["symbol"])), to_float(settings.near_target_pct)) for r in rows]
    return {"success": True, "data": data}


@router.post("", summary="加入觀察名單（同代碼同市場已存在則視為更新）")
async def add_watchlist(payload: WatchlistIn, db=Depends(get_db)):
    if payload.market not in ("tw", "us"):
        raise HTTPException(400, "market 必須為 tw 或 us")
    if payload.target_price is None or payload.target_price <= 0:
        raise HTTPException(400, "目標買進價必須大於 0")

    symbol = payload.symbol.strip().upper()
    repo = PortfolioRepository(db)
    row, created = await repo.upsert_watchlist({
        "market": payload.market, "symbol": symbol, "name": (payload.name or symbol).strip(),
        "target_price": D(payload.target_price), "note": payload.note,
    })
    settings = Settings.from_row(await repo.get_settings())
    quotes = await _quotes_for([row])
    return {
        "success": True,
        "data": _watch_out(row, quotes.get((row["market"], row["symbol"])), to_float(settings.near_target_pct)),
        "message": "已加入觀察名單" if created else "該股已在觀察名單中，已更新目標價與備註",
    }


@router.put("/{watch_id}", summary="編輯觀察紀錄（目標價／備註）")
async def update_watchlist(watch_id: int, payload: WatchlistUpdate, db=Depends(get_db)):
    if payload.target_price is not None and payload.target_price <= 0:
        raise HTTPException(400, "目標買進價必須大於 0")
    repo = PortfolioRepository(db)
    patch = {}
    if payload.target_price is not None:
        patch["target_price"] = D(payload.target_price)
    if payload.note is not None:
        patch["note"] = payload.note
    if payload.name is not None and payload.name.strip():
        patch["name"] = payload.name.strip()
    row = await repo.update_watchlist(watch_id, patch)
    if not row:
        raise HTTPException(404, "找不到觀察紀錄")
    settings = Settings.from_row(await repo.get_settings())
    quotes = await _quotes_for([row])
    return {
        "success": True,
        "data": _watch_out(row, quotes.get((row["market"], row["symbol"])), to_float(settings.near_target_pct)),
        "message": "已更新觀察紀錄",
    }


@router.delete("/{watch_id}", summary="移除觀察紀錄（不影響任何交易紀錄）")
async def delete_watchlist(watch_id: int, db=Depends(get_db)):
    ok = await PortfolioRepository(db).delete_watchlist(watch_id)
    if not ok:
        raise HTTPException(404, "找不到觀察紀錄")
    return {"success": True, "message": "已從觀察名單移除"}
