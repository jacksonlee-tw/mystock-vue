from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from config import get_target_stocks, save_target_stocks
from services.stock_service import (
    discover_available_stocks,
    get_stock_chart_payload,
    aggregate_stock_data,
    load_stock_json,
    get_heatmap_data
)

router = APIRouter(prefix="/api/v1/stocks", tags=["Stocks"])

class TrackedStockAddRequest(BaseModel):
    stock_id: str

@router.get("", summary="取得目前系統中所有可用的股票資料庫與其元資料")
def list_stocks():
    stocks = discover_available_stocks()
    return {"success": True, "data": stocks}

@router.get("/tracked", summary="取得目前追蹤的股票清單")
def get_tracked_stocks():
    codes = get_target_stocks()
    return {"success": True, "data": codes}

@router.get("/heatmap", summary="取得全市場熱力圖資料")
def get_heatmap(period: str = Query("daily", description="聚合週期: daily, weekly, monthly")):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")
    data = get_heatmap_data(period=period)
    return {"success": True, "data": data}

@router.post("/tracked", summary="新增追蹤股票代號")
def add_tracked_stock(req: TrackedStockAddRequest):
    stock_id = req.stock_id.strip()
    if not stock_id:
        raise HTTPException(status_code=400, detail="股票代號不可為空")
        
    current = get_target_stocks()
    if stock_id in current:
        return {"success": True, "message": "此股票已在追蹤清單中", "data": current}
        
    current.append(stock_id)
    save_target_stocks(current)
    return {"success": True, "message": f"已新增追蹤股票 {stock_id}", "data": current}

@router.delete("/tracked/{stock_id}", summary="移除追蹤股票代號")
def remove_tracked_stock(stock_id: str):
    stock_id = stock_id.strip()
    current = get_target_stocks()
    if stock_id not in current:
        raise HTTPException(status_code=404, detail="追蹤清單中找不到此股票代號")
        
    updated = [s for s in current if s != stock_id]
    save_target_stocks(updated)
    return {"success": True, "message": f"已移除追蹤股票 {stock_id}", "data": updated}

@router.get("/{stock_id}/chart-data", summary="取得單一股票的圖表專用格式資料")
def get_chart_data(
    stock_id: str,
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(3, description="時間範圍月份數: 1, 3, 6, 12 等")
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")
        
    payload = get_stock_chart_payload(stock_id, period=period, months=months)
    if "error" in payload:
        raise HTTPException(status_code=404, detail=payload["error"])
        
    return {"success": True, "data": payload}

@router.get("/{stock_id}", summary="取得單一股票詳細歷史交易明細記錄")
def get_stock_detail(
    stock_id: str,
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(3, description="時間範圍月份數")
):
    raw_data = load_stock_json(stock_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail=f"找不到股票 {stock_id} 的數據資料")
        
    aggregated = aggregate_stock_data(raw_data, period=period, months=months)
    return {
        "success": True,
        "stock_id": stock_id,
        "period": period,
        "months": months,
        "total_records": len(aggregated),
        "data": aggregated
    }
