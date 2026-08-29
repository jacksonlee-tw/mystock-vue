import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1.endpoints.ai_analysis import router as ai_analysis_router
from api.v1.endpoints.alerts import router as alerts_router
from api.v1.endpoints.cashflow import cashflow_router, dividend_router
from api.v1.endpoints.exchange_rates import router as exchange_rates_router
from api.v1.endpoints.fetch import router as fetch_router
from api.v1.endpoints.fundamentals import router as fundamentals_router
from api.v1.endpoints.indices import router as indices_router
from api.v1.endpoints.investment_notes import router as investment_notes_router
from api.v1.endpoints.market import router as market_router
from api.v1.endpoints.markets import router as markets_router
from api.v1.endpoints.notify_admin import router as notify_admin_router
from api.v1.endpoints.notify_admin import session_router as notify_session_router
from api.v1.endpoints.notify_public import router as notify_public_router
from api.v1.endpoints.notify_self import router as notify_self_router
from api.v1.endpoints.performance import router as performance_router
from api.v1.endpoints.portfolio import router as portfolio_router
from api.v1.endpoints.portfolio_settings import router as portfolio_settings_router
from api.v1.endpoints.schedule import router as schedule_router
from api.v1.endpoints.stocks import router as stocks_router
from api.v1.endpoints.strategies import router as strategies_router
from api.v1.endpoints.transactions import router as transactions_router
from api.v1.endpoints.watchlist import router as watchlist_router
from config import CORS_ORIGINS
from core.exceptions import SymbolNotFoundException
from core.owner_auth import OwnerUnauthorizedException
from db.session import dispose_engine
from notify.security import (
    ChannelUnavailableException,
    NotifyForbiddenException,
    NotifyNotFoundException,
    NotifyUnauthorizedException,
    NotifyValidationException,
    PreferenceWideningException,
)
from services.backfill import run_startup_backfill
from services.scheduler import create_scheduler
from services.tracking_service import diff_env_vs_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mystock-backend")

async def _run_startup_tracking_reconcile():
    """啟動對帳（追蹤與觀察名單整合規劃書 §4.3／§12.5）：比對 .env 與 DB 的追蹤代碼，
    只印警告不自動修改（避免啟動時偷改使用者設定）；發現差異時提示改用
    `scripts/sync_tracking_env.py` 手動修復。查詢本身失敗（例如 Postgres 未部署）
    只記警告，不影響服務啟動。"""
    for market in ("tw", "us"):
        diff = await diff_env_vs_db(market)
        if diff["checked"] and not diff["in_sync"]:
            logger.warning(
                "[追蹤清單] 啟動對帳發現 .env 與 DB 不同步（market=%s）：only_in_env=%s, only_in_db=%s，"
                "如需修復請執行 scripts/sync_tracking_env.py",
                market, diff["only_in_env"], diff["only_in_db"],
            )

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    asyncio.create_task(run_startup_backfill())  # 背景執行，缺漏回補不阻塞服務啟動（見 phase3_5 設計文件第 3.1 節）
    asyncio.create_task(_run_startup_tracking_reconcile())  # 背景執行，只印警告不阻塞服務啟動
    yield
    scheduler.shutdown(wait=False)
    await dispose_engine()

app = FastAPI(
    title="MyStock 股市三大法人與籌碼分析 API 服務",
    description="提供台灣股市三大法人買賣超、融資融券、K線圖歷史數據聚合與 TWSE 自動抓取服務",
    version="1.0.0",
    lifespan=lifespan
)

# ── CORS 設定 ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 註冊路由 ──────────────────────────────────────────────────────────────
app.include_router(stocks_router)
app.include_router(fetch_router)
app.include_router(markets_router)
app.include_router(market_router)
app.include_router(indices_router)
app.include_router(alerts_router)
app.include_router(watchlist_router)
app.include_router(notify_session_router)
app.include_router(notify_admin_router)
app.include_router(notify_public_router)
app.include_router(notify_self_router)
app.include_router(ai_analysis_router)
app.include_router(investment_notes_router)
app.include_router(transactions_router)
app.include_router(portfolio_router)
app.include_router(portfolio_settings_router)
app.include_router(performance_router)
app.include_router(dividend_router)
app.include_router(cashflow_router)
app.include_router(exchange_rates_router)
app.include_router(fundamentals_router)
app.include_router(schedule_router)
app.include_router(strategies_router)

@app.exception_handler(SymbolNotFoundException)
async def symbol_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False,
        "error": {"code": "SYMBOL_NOT_FOUND", "message": str(exc)}
    })

@app.exception_handler(OwnerUnauthorizedException)
async def owner_unauthorized_handler(request, exc):
    return JSONResponse(status_code=401, content={
        "success": False,
        "error": {"code": "OWNER_UNAUTHORIZED", "message": str(exc)}
    })

@app.exception_handler(NotifyUnauthorizedException)
async def notify_unauthorized_handler(request, exc):
    return JSONResponse(status_code=401, content={
        "success": False,
        "error": {"code": "NOTIFY_UNAUTHORIZED", "message": str(exc)}
    })

@app.exception_handler(NotifyForbiddenException)
async def notify_forbidden_handler(request, exc):
    return JSONResponse(status_code=403, content={
        "success": False,
        "error": {"code": "NOTIFY_FORBIDDEN", "message": str(exc)}
    })

@app.exception_handler(NotifyNotFoundException)
async def notify_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False,
        "error": {"code": "NOTIFY_NOT_FOUND", "message": str(exc)}
    })

@app.exception_handler(NotifyValidationException)
async def notify_validation_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False,
        "error": {"code": "NOTIFY_VALIDATION_ERROR", "message": str(exc)}
    })

@app.exception_handler(PreferenceWideningException)
async def notify_preference_widening_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False,
        "error": {"code": "NOTIFY_PREFERENCE_WIDENING", "message": str(exc)}
    })

@app.exception_handler(ChannelUnavailableException)
async def notify_channel_unavailable_handler(request, exc):
    return JSONResponse(status_code=503, content={
        "success": False,
        "error": {"code": "NOTIFY_CHANNEL_UNAVAILABLE", "message": str(exc)}
    })

@app.get("/health", summary="健康檢查端點", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "MyStock Backend API"}

if __name__ == "__main__":
    print("=" * 60)
    print("MyStock 股市分析 FastAPI 後端服務啟動中...")
    print("API 文件請開啟: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
