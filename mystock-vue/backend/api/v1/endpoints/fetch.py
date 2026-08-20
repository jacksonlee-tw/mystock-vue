from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.fetcher import fetch_status, run_fetch_process
from services.us_fetcher import run_us_fetch_process
from services.index_fetcher import get_index_definitions, run_index_fetch_process
from config import get_target_stocks, get_months_range

router = APIRouter(prefix="/api/v1/fetch", tags=["Fetcher"])

class FetchTriggerRequest(BaseModel):
    market: str = "tw"
    stocks: Optional[List[str]] = None
    months: Optional[int] = None
    # incremental: 只補最後一筆之後的缺口（全域同步用）
    # repair: 忽略既有資料，以完整區間重抓（單股重抓／補缺漏用）
    mode: str = "incremental"

@router.post("/trigger", summary="觸發資料抓取任務（背景執行）")
def trigger_fetch_task(req: FetchTriggerRequest, background_tasks: BackgroundTasks):
    snapshot = fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot
        }

    target_stocks = req.stocks if req.stocks else get_target_stocks(market=req.market)
    months = req.months if req.months else get_months_range()

    mode = req.mode if req.mode in ("incremental", "repair") else "incremental"

    # 單股重抓彈窗（前端 RefetchStockDialog）不曉得目前看的是個股還是大盤指數，可能把指數代號
    # （例如 IXIC、TWII）當成一般股票代號送進來。指數不能走個股爬蟲：少了 external_symbol 的
    # '^' 前綴（yfinance 查不到對應標的）、JSON 落地目錄也不同（data/{market}/_indices/），
    # 這裡先過濾出真正屬於指數定義檔的代號，改導去指數抓取流程，其餘才視為一般股票代號。
    index_codes = {d.code for d in get_index_definitions(req.market)}
    requested_index_codes = [s for s in target_stocks if s in index_codes]
    stock_only = [s for s in target_stocks if s not in index_codes]

    if requested_index_codes:
        background_tasks.add_task(run_index_fetch_process, market=req.market,
                                  codes=requested_index_codes, months=months, mode=mode)

    if stock_only:
        if req.market == "us":
            background_tasks.add_task(run_us_fetch_process, target_stocks=stock_only,
                                      months=months, mode=mode)
        else:
            background_tasks.add_task(run_fetch_process, target_stocks=stock_only,
                                      months=months, mode=mode)

    mode_label = "重新抓取" if mode == "repair" else "增量更新"
    return {
        "success": True,
        "message": f"已在背景啟動{mode_label}任務 - 目標股票: {target_stocks}, 範圍: 近 {months} 個月",
        "data": fetch_status.get_snapshot()
    }

@router.get("/status", summary="查詢抓取任務目前進度與日誌")
def get_fetch_status():
    return {
        "success": True,
        "data": fetch_status.get_snapshot()
    }
