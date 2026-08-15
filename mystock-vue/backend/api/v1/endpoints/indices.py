"""大盤指數 API（見 docs/10.加權指數/大盤指數功能規劃書.md 第九節）。

回應信封與既有端點一致：{"success": bool, "data": ..., "message"?: ..., "error"?: {...}}。
找不到資料時拋 SymbolNotFoundException，由 main.py 的全域 handler 轉成 404 / SYMBOL_NOT_FOUND，
與 /api/v1/stocks 系列端點的慣例一致。

涵蓋 Phase 1（指數清單、首頁總覽、圖表資料、手動觸發抓取）＋ Phase 5（多指數比較、類股輪動）。
市場寬度／大盤法人等端點依賴尚未實作的 Phase 3 資料，暫不建立空殼端點。

路由順序注意：`/overview`、`/sync`、`/compare`、`/sectors` 都是固定路徑，必須宣告在
`/{code}`、`/{code}/chart-data` 之前，否則 FastAPI 會把這些固定字串誤判成 code 參數。
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from core.exceptions import SymbolNotFoundException
from services.fetcher import fetch_status
from services.index_fetcher import get_index_definition, run_index_fetch_process
from services.index_service import (
    build_rebased_series,
    discover_available_indices,
    get_index_chart_data,
    get_index_overview,
    get_sector_overview,
)

router = APIRouter(prefix="/api/v1/indices", tags=["Indices"])


class IndexSyncRequest(BaseModel):
    market: Optional[str] = None
    codes: Optional[List[str]] = None
    months: Optional[int] = None
    # incremental: 只補最後一筆資料之後的缺口 / repair: 忽略既有資料以完整區間重抓
    mode: str = "incremental"


@router.get("", summary="取得支援的大盤指數清單")
async def list_indices(market: Optional[str] = Query(None, description="市場代碼過濾，例如 tw, us")):
    data = await discover_available_indices(market)
    return {"success": True, "data": data}


@router.get("/overview", summary="首頁／熱力圖大盤概況：一次取得所有指數的最新報價、漲跌與 Sparkline")
async def get_overview(
    market: Optional[str] = Query(None, description="市場代碼過濾，例如 tw, us"),
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")
    data = await get_index_overview(market, period=period)
    return {"success": True, "data": data}


@router.post("/sync", summary="手動觸發指數資料同步（背景執行）")
def trigger_index_sync(req: IndexSyncRequest, background_tasks: BackgroundTasks):
    snapshot = fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "已有抓取任務執行中，請勿重複觸發"},
            "data": snapshot,
        }

    mode = req.mode if req.mode in ("incremental", "repair") else "incremental"
    background_tasks.add_task(
        run_index_fetch_process,
        market=req.market, codes=req.codes, months=req.months, mode=mode, trigger_type="manual",
    )

    mode_label = "重新抓取" if mode == "repair" else "增量更新"
    return {
        "success": True,
        "message": f"已在背景啟動指數{mode_label}任務" + (f"（市場: {req.market}）" if req.market else ""),
        "data": fetch_status.get_snapshot(),
    }


@router.get("/compare", summary="多指數 Rebase=100 比較")
async def compare_indices(
    codes: str = Query(..., description="逗號分隔的指數代號，例如 TWII,SOX"),
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(12, description="時間範圍月份數"),
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 檔指數才能比較")

    items = []
    for c in code_list:
        definition = get_index_definition(c)
        if not definition:
            raise SymbolNotFoundException(f"找不到指數 {c}")
        items.append({"code": definition.code, "market": definition.market, "kind": "index",
                       "label": definition.short_name})

    result = await build_rebased_series(items, period=period, months=months)
    return {"success": True, "data": result}


@router.get("/sectors", summary="台股類股指數當日表現排行（輪動）")
async def get_sectors(market: str = Query("tw", description="目前僅支援 tw")):
    if market != "tw":
        return {"success": True, "data": [], "message": "類股指數目前僅支援台股（規劃書 §8.1）"}
    data = await get_sector_overview()
    return {"success": True, "data": data}


@router.get("/{code}/chart-data", summary="取得單一指數的圖表專用格式資料")
async def get_chart_data(
    code: str,
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(3, description="時間範圍月份數: 1, 3, 6, 12 等"),
    market: str = Query("tw", description="市場代碼"),
):
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")

    payload = await get_index_chart_data(code, period=period, months=months, market=market)
    if "error" in payload:
        raise SymbolNotFoundException(payload["error"])

    return {"success": True, "data": payload}


@router.get("/{code}", summary="取得單一指數歷史明細數據")
async def get_index_detail(
    code: str,
    period: str = Query("daily", description="聚合週期: daily, weekly, monthly"),
    months: int = Query(3, description="時間範圍月份數"),
    market: str = Query("tw", description="市場代碼"),
):
    from services.stock_service import aggregate_stock_data, load_stock_data

    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="period 必須為 daily, weekly, 或 monthly")

    raw_data = await load_stock_data(code, market, kind="index")
    if not raw_data:
        raise SymbolNotFoundException(f"找不到指數 {code} 的數據資料")

    aggregated = aggregate_stock_data(raw_data, period=period, months=months)
    return {
        "success": True,
        "code": code,
        "period": period,
        "months": months,
        "market": market,
        "total_records": len(aggregated),
        "data": aggregated,
    }
