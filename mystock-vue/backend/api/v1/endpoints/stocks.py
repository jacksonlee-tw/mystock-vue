from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
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

# 產業標籤同步是否正在執行中（大盤指數功能規劃書 §8.2）：獨立於 services/fetcher.py 的
# fetch_status，因為這是低頻率、非「每日抓取」性質的背景工作，不需要共用同一個互斥旗標。
_industry_sync_running = False

# 台股全市場代碼主檔同步是否正在執行中，理由同上，跟產業標籤同步各自獨立一個旗標
# （兩者來源不同的 TWSE/TPEx OpenAPI，沒有理由互相卡住）。
_symbol_master_sync_running = False

class TrackedStockAddRequest(BaseModel):
    stock_id: Optional[str] = None
    stock_ids: Optional[List[str]] = None

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

@router.get("/industries", summary="取得個股產業標籤對照表（大盤指數功能規劃書 §8.2）")
async def get_industries(market: str = Query("tw", description="市場代碼")):
    from services.industry_fetcher import load_industries_json
    return {"success": True, "data": load_industries_json(market)}

@router.post("/industries/sync", summary="手動觸發產業標籤同步（背景執行）")
async def trigger_industry_sync(background_tasks: BackgroundTasks, market: str = Query("tw")):
    global _industry_sync_running
    if _industry_sync_running:
        return {
            "success": False,
            "error": {"code": "SYNC_IN_PROGRESS", "message": "產業標籤同步已在執行中，請勿重複觸發"},
        }

    def _run():
        global _industry_sync_running
        _industry_sync_running = True
        try:
            from services.industry_fetcher import sync_tw_industries, sync_us_industries
            if market == "us":
                sync_us_industries(get_target_stocks(market="us"))
            else:
                sync_tw_industries()
        finally:
            _industry_sync_running = False

    background_tasks.add_task(_run)
    return {"success": True, "message": f"已在背景啟動產業標籤同步任務（市場: {market}）"}

@router.post("/symbols/sync", summary="手動觸發全市場代碼／名稱主檔同步（背景執行）")
async def trigger_symbol_master_sync(background_tasks: BackgroundTasks, market: str = Query("tw")):
    global _symbol_master_sync_running
    if _symbol_master_sync_running:
        return {
            "success": False,
            "error": {"code": "SYNC_IN_PROGRESS", "message": "代碼主檔同步已在執行中，請勿重複觸發"},
        }

    async def _run():
        global _symbol_master_sync_running
        _symbol_master_sync_running = True
        try:
            from services.symbol_master_fetcher import sync_tw_symbol_master, sync_us_symbol_master
            if market == "us":
                await sync_us_symbol_master()
            else:
                await sync_tw_symbol_master()
        finally:
            _symbol_master_sync_running = False

    background_tasks.add_task(_run)
    return {"success": True, "message": f"已在背景啟動全市場代碼清單同步任務（市場: {market}）"}

@router.get("/symbols", summary="分頁瀏覽／篩選全市場代碼主檔")
async def list_symbols(
    market: str = Query("tw", description="市場代碼"),
    q: Optional[str] = Query(None, description="代號前綴或名稱片段"),
    industry_code: Optional[str] = Query(None, description="產業別代碼過濾"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    from repositories.stock_repository import StockRepository

    offset = (page - 1) * page_size
    items, total = await StockRepository().list_symbols_page(
        market_type=market, query=q, industry_code=industry_code, offset=offset, limit=page_size
    )
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }

@router.get("/symbols/industry-options", summary="取得代碼主檔篩選用的產業別下拉選項")
async def list_symbol_industry_options(market: str = Query("tw", description="市場代碼")):
    from repositories.stock_repository import StockRepository

    options = await StockRepository().list_distinct_industries(market_type=market)
    return {"success": True, "data": options}

@router.post("/tracked", summary="新增追蹤股票代號（支援批次：帶 stock_ids 陣列一次新增多檔）")
async def add_tracked_stock(req: TrackedStockAddRequest, market: str = Query("tw")):
    raw_codes = req.stock_ids if req.stock_ids else ([req.stock_id] if req.stock_id else [])
    codes = list(dict.fromkeys(c.strip() for c in raw_codes if c and c.strip()))  # trim + 去重，保留順序
    if not codes:
        raise HTTPException(status_code=400, detail="股票代號不可為空")

    current = get_target_stocks(market=market)
    already = [c for c in codes if c in current]
    new_codes = [c for c in codes if c not in current]

    if new_codes:
        current = current + new_codes
        save_target_stocks(current, market=market)

    # 對新加入的代號做一次主檔驗證，查不到的仍照樣加入（不阻斷流程），只在回應中標記出來
    # 讓前端可以提示使用者確認代號是否正確（見 markets/tw.py validate_symbols()）。
    unknown: List[str] = []
    if new_codes:
        try:
            adapter = get_adapter(market)
            validation = await adapter.validate_symbols(new_codes)
            unknown = [c for c in new_codes if validation.get(c, {}).get("status") != "resolved"]
        except ValueError:
            pass

    if new_codes:
        message = f"已新增 {len(new_codes)} 檔追蹤股票"
        if already:
            message += f"，{len(already)} 檔已在清單中"
    else:
        message = "所選股票皆已在追蹤清單中"

    return {
        "success": True,
        "message": message,
        "data": await _build_tracked_details(current, market),
        "added": new_codes,
        "already_tracked": already,
        "unknown": unknown,
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

@router.get("/{stock_id}/vs-index", summary="個股 vs 大盤指數 Rebase=100 疊圖比較")
async def get_stock_vs_index(
    stock_id: str,
    market: str = Query("tw", description="市場代碼"),
    benchmark: Optional[str] = Query(None, description="基準指數代號；未提供時 tw 預設 TWII、us 預設 GSPC"),
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(12, description="時間範圍月份數"),
):
    from services.index_fetcher import get_index_definition
    from services.index_service import build_rebased_series

    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")

    benchmark_code = benchmark or ("TWII" if market == "tw" else "GSPC")
    definition = get_index_definition(benchmark_code)
    if not definition:
        raise HTTPException(status_code=400, detail=f"找不到基準指數 {benchmark_code}")

    items = [
        {"code": stock_id, "market": market, "kind": "stock", "label": stock_id},
        {"code": definition.code, "market": definition.market, "kind": "index", "label": definition.short_name},
    ]
    result = await build_rebased_series(items, period=period, months=months)
    return {"success": True, "data": result, "benchmark": benchmark_code}


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
