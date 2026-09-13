"""個股新聞與 PTT 討論度端點（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md §8）。

回應信封沿用專案慣例 `{"success": bool, "data": ..., "message"?: ..., "error"?: {"code","message"}}`；
`sentiment_score`/`sentiment_label` 欄位允許為 NULL——新抓到的新聞要等
`POST /sentiment/trigger` 跑過批次評分才會填值，前端可依此顯示「尚未評分」而非誤判為缺值錯誤。
"""
from fastapi import APIRouter, BackgroundTasks

from core.exceptions import SymbolNotFoundException
from services.news_analytics import get_sentiment_summary
from services.news_config import load_news_sources_config
from services.news_fetcher import fetch_status, run_news_fetch
from services.news_sentiment import score_pending_news, sentiment_fetch_status

router = APIRouter(prefix="/api/v1/news", tags=["News"])


@router.get("/sources", summary="目前納入哪些新聞/社群來源與啟用狀態")
def get_news_sources():
    config = load_news_sources_config()
    return {
        "success": True,
        "data": {
            "enabled_count": len(config.enabled_sources()),
            "sources": [
                {
                    "id": s.id, "name": s.name, "kind": s.kind,
                    "enabled": s.enabled, "weight": s.weight,
                }
                for s in config.sources
            ],
        },
    }


@router.post("/trigger", summary="手動觸發新聞與 PTT 討論度抓取任務（背景執行）")
def trigger_news_fetch(background_tasks: BackgroundTasks):
    snapshot = fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "新聞抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot,
        }
    background_tasks.add_task(run_news_fetch, trigger_type="manual")
    return {"success": True, "message": "已在背景啟動新聞與 PTT 討論度抓取任務", "data": fetch_status.get_snapshot()}


@router.get("/status", summary="查詢新聞抓取任務目前進度與日誌")
def get_news_fetch_status():
    return {"success": True, "data": fetch_status.get_snapshot()}


@router.post("/sentiment/trigger", summary="手動觸發新聞情緒批次評分任務（背景執行，ADR-P4-08：LLM 批次評分）")
def trigger_sentiment_scoring(background_tasks: BackgroundTasks):
    snapshot = sentiment_fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "SCORING_IN_PROGRESS", "message": "情緒評分任務已在執行中，請勿重複觸發"},
            "data": snapshot,
        }
    background_tasks.add_task(score_pending_news, trigger_type="manual")
    return {"success": True, "message": "已在背景啟動新聞情緒批次評分任務", "data": sentiment_fetch_status.get_snapshot()}


@router.get("/sentiment/status", summary="查詢情緒評分任務目前進度與日誌")
def get_sentiment_scoring_status():
    return {"success": True, "data": sentiment_fetch_status.get_snapshot()}


@router.get("/{symbol}/sentiment-summary", summary="查詢個股 5 日加權情緒分數與 Buzz Surge（§4.3）")
async def get_stock_sentiment_summary(symbol: str, market: str = "tw"):
    from repositories.stock_repository import StockRepository

    if not await StockRepository().get_symbol(symbol):
        raise SymbolNotFoundException(f"找不到股票 {symbol}")

    data = await get_sentiment_summary(symbol, market)
    return {"success": True, "data": data}


@router.get("/{symbol}", summary="分頁查詢個股新聞與情緒評分")
async def get_stock_news(
    symbol: str,
    market: str = "tw",
    page: int = 1,
    page_size: int = 20,
    include_duplicates: bool = False,
):
    from db.session import get_async_session
    from repositories.news_repository import NewsRepository
    from repositories.stock_repository import StockRepository

    if not await StockRepository().get_symbol(symbol):
        raise SymbolNotFoundException(f"找不到股票 {symbol}")

    page = max(1, page)
    page_size = max(1, min(100, page_size))

    async with get_async_session() as session:
        repo = NewsRepository(session)
        items, total = await repo.list_by_symbol(
            symbol=symbol, market_type=market, include_duplicates=include_duplicates,
            page=page, page_size=page_size,
        )

    return {
        "success": True,
        "data": {
            "symbol": symbol, "page": page, "page_size": page_size, "total": total,
            "items": items,
        },
    }
