"""總體經濟與大盤環境端點（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §5、§8）。

回應信封沿用專案慣例 `{"success": bool, "data": ..., "message"?: ..., "error"?: {"code","message"}}`。
`GET /indicators*` 一律只回傳 `release_date <= 今天` 的最新值（ADR-P4-05，比照月營收 look-ahead
bias 防線）——月頻指標（CPI／非農／聯邦資金利率）公布日落後所屬月份數週，不得誤用尚未公布的期間。
"""
from datetime import date

from fastapi import APIRouter, BackgroundTasks

from db.session import get_async_session
from repositories.news_repository import NewsRepository
from services.macro_analytics import get_market_regime
from services.macro_fetcher import FRED_SERIES_MAP, fetch_status, run_macro_fetch

router = APIRouter(prefix="/api/v1/macro", tags=["Macro"])


@router.post("/trigger", summary="手動觸發總經指標（FRED + DXY）抓取任務（背景執行）")
def trigger_macro_fetch(background_tasks: BackgroundTasks):
    snapshot = fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "總經指標抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot,
        }
    background_tasks.add_task(run_macro_fetch, trigger_type="manual")
    return {"success": True, "message": "已在背景啟動總經指標抓取任務", "data": fetch_status.get_snapshot()}


@router.get("/status", summary="查詢總經指標抓取任務目前進度與日誌")
def get_macro_fetch_status():
    return {"success": True, "data": fetch_status.get_snapshot()}


@router.get("/indicators", summary="查詢全部總經指標目前可見的最新值（§5.1 point-in-time 對齊）")
async def get_all_macro_indicators():
    today = date.today()
    async with get_async_session() as session:
        repo = NewsRepository(session)
        data = {
            code: await repo.get_latest_visible_indicator(indicator_code=code, as_of=today)
            for code in FRED_SERIES_MAP
        }
    return {"success": True, "data": data}


@router.get("/indicators/{indicator_code}", summary="查詢單一總經指標目前可見的最新值")
async def get_macro_indicator(indicator_code: str):
    indicator_code = indicator_code.upper()
    async with get_async_session() as session:
        value = await NewsRepository(session).get_latest_visible_indicator(
            indicator_code=indicator_code, as_of=date.today(),
        )
    if value is None:
        return {
            "success": True, "data": None,
            "message": f"{indicator_code} 目前尚無可見資料（可能尚未抓取，或所有紀錄皆晚於今日公布）",
        }
    return {"success": True, "data": value}


@router.get("/indicators/{indicator_code}/series", summary="查詢單一總經指標的近期已公布序列（供前端 Sparkline，§11）")
async def get_macro_indicator_series(indicator_code: str, limit: int = 30):
    indicator_code = indicator_code.upper()
    limit = max(1, min(100, limit))
    async with get_async_session() as session:
        series = await NewsRepository(session).get_visible_indicator_series(
            indicator_code=indicator_code, as_of=date.today(), limit=limit,
        )
    return {"success": True, "data": {"indicator_code": indicator_code, "series": series}}


@router.get("/market-regime/{market}", summary="查詢大盤指數 20MA/60MA 位階（§5.2 全域鎖底層查詢）")
async def get_market_regime_endpoint(market: str):
    data = await get_market_regime(market)
    return {"success": True, "data": data}
