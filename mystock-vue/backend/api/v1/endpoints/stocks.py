from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from core.exceptions import SymbolNotFoundException
from config import get_target_stocks, save_target_stocks
from markets import get_adapter
from services.stock_service import (
    discover_available_stocks,
    get_stock_chart_payload,
    aggregate_stock_data,
    load_stock_data,
    get_heatmap_data
)

router = APIRouter(prefix="/api/v1/stocks", tags=["Stocks"])

class TrackedStockAddRequest(BaseModel):
    stock_id: str

async def _build_tracked_details(codes: List[str], market: str) -> List[Dict[str, Any]]:
    """組出追蹤清單的資料涵蓋範圍，並統計缺少價格的天數（供前端顯示缺漏警示）。"""
    details = []
    for code in codes:
        stock_data = await load_stock_data(code, market)
        dates = sorted(stock_data.keys()) if stock_data else []
        details.append({
            "code": code,
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "count": len(dates),
            "missing_price_days": sum(1 for d in dates if not stock_data[d].get("close")),
        })
    return details

@router.get("", summary="取得目前系統中所有可用的股票資料庫與其元資料")
async def list_stocks(market: Optional[str] = Query(None, description="市場代碼過濾")):
    stocks = await discover_available_stocks()
    if market:
        stocks = [s for s in stocks if s.get("market") == market]
    return {"success": True, "data": stocks}

@router.get("/tracked", summary="取得目前追蹤的股票清單")
async def get_tracked_stocks(market: str = Query("tw", description="市場代碼")):
    codes = get_target_stocks(market=market)
    return {"success": True, "data": await _build_tracked_details(codes, market)}

@router.get("/heatmap", summary="取得全市場熱力圖資料")
async def get_heatmap(
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    market: Optional[str] = Query(None, description="過濾指定市場 (例如 tw, us)")
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")
    data = await get_heatmap_data(period=period, market=market)
    return {"success": True, "data": data}

@router.get("/industries", summary="取得產業分類資料")
async def get_industries(market: str = Query("tw", description="市場代碼")):
    from services.industry_fetcher import load_industries_json
    return {"success": True, "data": load_industries_json(market)}

@router.post("/tracked", summary="新增追蹤股票代號")
async def add_tracked_stock(req: TrackedStockAddRequest, market: str = Query("tw")):
    stock_id = req.stock_id.strip()
    if not stock_id:
        raise HTTPException(status_code=400, detail="股票代號不可為空")

    current = get_target_stocks(market=market)
    if stock_id in current:
        return {"success": True, "message": "此股票已在追蹤清單中", "data": current}

    current.append(stock_id)
    save_target_stocks(current, market=market)

    # Return the new list with dates so frontend can update correctly
    return {
        "success": True,
        "message": f"已新增追蹤股票 {stock_id}",
        "data": await _build_tracked_details(current, market)
    }

@router.delete("/tracked/{stock_id}", summary="移除追蹤股票代號")
async def remove_tracked_stock(stock_id: str, market: str = Query("tw")):
    stock_id = stock_id.strip()
    current = get_target_stocks(market=market)
    if stock_id not in current:
        raise SymbolNotFoundException("追蹤清單中找不到此股票代號")

    updated = [s for s in current if s != stock_id]
    save_target_stocks(updated, market=market)

    # Return the new list with dates so frontend can update correctly
    return {
        "success": True,
        "message": f"已移除追蹤股票 {stock_id}",
        "data": await _build_tracked_details(updated, market)
    }

@router.get("/{stock_id}/chart-data", summary="取得單一股票的圖表專用格式資料")
async def get_chart_data(
    stock_id: str,
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(3, description="時間範圍月份數: 1, 3, 6, 12 等"),
    market: str = Query("tw", description="市場代碼")
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")

    payload = await get_stock_chart_payload(stock_id, period=period, months=months, market=market)
    if "error" in payload:
        raise SymbolNotFoundException(payload["error"])

    try:
        adapter = get_adapter(market)
        payload["meta"] = adapter.meta.__dict__
        payload["metrics"] = [m.__dict__ for m in adapter.metrics]
    except ValueError:
        pass

    return {"success": True, "data": payload}

@router.get("/{stock_id}", summary="取得單一股票詳細歷史交易明細記錄")
async def get_stock_detail(
    stock_id: str,
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(3, description="時間範圍月份數"),
    market: str = Query("tw", description="市場代碼")
):
    raw_data = await load_stock_data(stock_id, market)
    if not raw_data:
        raise SymbolNotFoundException(f"找不到股票 {stock_id} 的數據資料")

    aggregated = aggregate_stock_data(raw_data, period=period, months=months)
    return {
        "success": True,
        "stock_id": stock_id,
        "period": period,
        "months": months,
        "market": market,
        "total_records": len(aggregated),
        "data": aggregated
    }
