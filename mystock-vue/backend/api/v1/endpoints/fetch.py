from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services.fetcher import fetch_status, run_fetch_process
from services.us_fetcher import run_us_fetch_process
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

    if req.market == "us":
        background_tasks.add_task(run_us_fetch_process, target_stocks=target_stocks,
                                  months=months, mode=mode)
    else:
        background_tasks.add_task(run_fetch_process, target_stocks=target_stocks,
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
