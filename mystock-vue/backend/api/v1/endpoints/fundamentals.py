from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from config import get_months_range, get_quarters_range, get_target_stocks
from core.exceptions import SymbolNotFoundException
from services.mops_fetcher import load_stock_revenue, mops_fetch_status, run_fetch_monthly_revenue
from services.mops_eps_fetcher import eps_fetch_status, load_stock_eps, run_fetch_quarterly_eps

router = APIRouter(prefix="/api/v1/fundamentals", tags=["Fundamentals"])


class RevenueFetchTriggerRequest(BaseModel):
    stocks: Optional[List[str]] = None
    months: Optional[int] = None
    force: bool = False


@router.post("/revenue/trigger", summary="觸發月營收抓取任務（背景執行）")
def trigger_revenue_fetch(req: RevenueFetchTriggerRequest, background_tasks: BackgroundTasks):
    snapshot = mops_fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "月營收抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot
        }

    target_stocks = req.stocks if req.stocks else get_target_stocks(market="tw")
    months = req.months if req.months else get_months_range()

    background_tasks.add_task(
        run_fetch_monthly_revenue,
        target_stocks=target_stocks,
        months=months,
        force=req.force,
        trigger_type="manual",
    )
    return {
        "success": True,
        "message": f"已在背景啟動月營收抓取任務 - 目標股票: {target_stocks}, 範圍: 近 {months} 個月",
        "data": mops_fetch_status.get_snapshot()
    }


@router.get("/revenue/status", summary="查詢月營收抓取任務目前進度與日誌")
def get_revenue_fetch_status():
    return {
        "success": True,
        "data": mops_fetch_status.get_snapshot()
    }


@router.get("/revenue/{stock_id}", summary="查詢單一股票的月營收資料")
def get_stock_revenue(stock_id: str):
    data = load_stock_revenue(stock_id)
    if not data:
        raise SymbolNotFoundException(f"找不到股票 {stock_id} 的月營收資料")
    return {
        "success": True,
        "data": data
    }


class EpsFetchTriggerRequest(BaseModel):
    stocks: Optional[List[str]] = None
    quarters: Optional[int] = None
    force: bool = False


@router.post("/eps/trigger", summary="觸發季報 EPS 抓取任務（背景執行）")
def trigger_eps_fetch(req: EpsFetchTriggerRequest, background_tasks: BackgroundTasks):
    snapshot = eps_fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "季報 EPS 抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot
        }

    target_stocks = req.stocks if req.stocks else get_target_stocks(market="tw")
    quarters = req.quarters if req.quarters else get_quarters_range()

    background_tasks.add_task(
        run_fetch_quarterly_eps,
        target_stocks=target_stocks,
        quarters=quarters,
        force=req.force,
        trigger_type="manual",
    )
    return {
        "success": True,
        "message": f"已在背景啟動季報 EPS 抓取任務 - 目標股票: {target_stocks}, 範圍: 近 {quarters} 季",
        "data": eps_fetch_status.get_snapshot()
    }


@router.get("/eps/status", summary="查詢季報 EPS 抓取任務目前進度與日誌")
def get_eps_fetch_status():
    return {
        "success": True,
        "data": eps_fetch_status.get_snapshot()
    }


@router.get("/eps/{stock_id}", summary="查詢單一股票的季報 EPS 資料")
def get_stock_eps(stock_id: str):
    data = load_stock_eps(stock_id)
    if not data:
        raise SymbolNotFoundException(f"找不到股票 {stock_id} 的季報 EPS 資料")
    return {
        "success": True,
        "data": data
    }
