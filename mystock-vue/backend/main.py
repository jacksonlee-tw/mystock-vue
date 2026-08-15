import asyncio
import logging
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from api.v1.endpoints.stocks import router as stocks_router
from api.v1.endpoints.fetch import router as fetch_router
from api.v1.endpoints.schedule import router as schedule_router
from api.v1.endpoints.markets import router as markets_router
from api.v1.endpoints.indices import router as indices_router
from api.v1.endpoints.alerts import router as alerts_router
from api.v1.endpoints.strategies import router as strategies_router
from api.v1.endpoints.fundamentals import router as fundamentals_router
from api.v1.endpoints.transactions import router as transactions_router
from api.v1.endpoints.portfolio import router as portfolio_router
from api.v1.endpoints.performance import router as performance_router
from api.v1.endpoints.cashflow import dividend_router as dividends_router, cashflow_router as cashflow_router
from api.v1.endpoints.watchlist import router as watchlist_router
from api.v1.endpoints.portfolio_settings import router as portfolio_settings_router
from api.v1.endpoints.notify_admin import router as notify_admin_router, session_router as notify_session_router
from api.v1.endpoints.notify_self import router as notify_self_router
from api.v1.endpoints.notify_public import router as notify_public_router
from core.exceptions import SymbolNotFoundException
from notify.security import (
    NotifyUnauthorizedException, NotifyForbiddenException, NotifyNotFoundException,
    NotifyValidationException, ChannelUnavailableException, PreferenceWideningException,
)
from db.session import dispose_engine
from services.scheduler import create_scheduler
from services.backfill import run_startup_backfill
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mystock-backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    asyncio.create_task(run_startup_backfill())  # 背景執行，缺漏回補不阻塞服務啟動（見 phase3_5 設計文件第 3.1 節）

    # ── 整合訊息通知平台（僅在 NOTIFY_ENABLED=true 時啟動；失敗不得拖垮既有服務，鐵則 R7）──
    try:
        from notify import config as notify_config
        if notify_config.is_enabled():
            from notify.dispatcher import start_dispatcher
            from notify import telegram_bot
            from notify.templating import seed_templates
            from db.session import get_async_session
            from repositories.notify_repository import NotifyRepository

            async with get_async_session() as _session:
                await seed_templates(NotifyRepository(_session))
                await _session.commit()
            await start_dispatcher()
            await telegram_bot.start()
            logger.info("[通知] 整合訊息通知平台已啟動")
        else:
            logger.info("[通知] NOTIFY_ENABLED=false，整合訊息通知平台不啟動")
    except Exception as exc:
        logger.warning("[通知] 通知平台啟動失敗（已靜默，既有服務不受影響）：%s", exc)

    yield

    try:
        from notify.dispatcher import stop_dispatcher
        from notify import telegram_bot
        await stop_dispatcher()
        await telegram_bot.stop()
    except Exception as exc:
        logger.warning("[通知] 通知平台關閉時發生例外（已忽略）：%s", exc)

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
app.include_router(schedule_router)
app.include_router(markets_router)
app.include_router(indices_router)
app.include_router(alerts_router)
app.include_router(strategies_router)
app.include_router(fundamentals_router)
# ── 個人投資記帳與績效追蹤模組（docs/8.個人投資記帳功能/）─────────────────
app.include_router(transactions_router)
app.include_router(portfolio_router)
app.include_router(performance_router)
app.include_router(dividends_router)
app.include_router(cashflow_router)
app.include_router(watchlist_router)
app.include_router(portfolio_settings_router)
app.include_router(notify_admin_router)
app.include_router(notify_session_router)
app.include_router(notify_self_router)
app.include_router(notify_public_router)

@app.exception_handler(SymbolNotFoundException)
async def symbol_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False,
        "error": {"code": "SYMBOL_NOT_FOUND", "message": str(exc)}
    })

# ── 整合訊息通知平台例外處理（§6.1、§7.3）────────────────────────────────
@app.exception_handler(NotifyUnauthorizedException)
async def notify_unauthorized_handler(request, exc):
    return JSONResponse(status_code=401, content={
        "success": False, "error": {"code": "NOTIFY_UNAUTHORIZED", "message": str(exc) or "未授權"}
    })

@app.exception_handler(NotifyForbiddenException)
async def notify_forbidden_handler(request, exc):
    return JSONResponse(status_code=403, content={
        "success": False, "error": {"code": "NOTIFY_FORBIDDEN", "message": str(exc) or "禁止存取"}
    })

@app.exception_handler(NotifyNotFoundException)
async def notify_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False, "error": {"code": "NOTIFY_NOT_FOUND", "message": str(exc) or "找不到資源"}
    })

@app.exception_handler(NotifyValidationException)
async def notify_validation_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False, "error": {"code": "NOTIFY_INVALID_INPUT", "message": str(exc) or "輸入不合法"}
    })

@app.exception_handler(PreferenceWideningException)
async def notify_widening_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False, "error": {"code": "NOTIFY_SCOPE_WIDENING", "message": str(exc) or "不得放寬授權範圍"}
    })

@app.exception_handler(ChannelUnavailableException)
async def notify_channel_unavailable_handler(request, exc):
    return JSONResponse(status_code=409, content={
        "success": False, "error": {"code": "NOTIFY_CHANNEL_UNAVAILABLE", "message": str(exc) or "管道目前無法使用"}
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
