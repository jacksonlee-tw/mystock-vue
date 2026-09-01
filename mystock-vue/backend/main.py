import asyncio
import logging
import os
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
from api.v1.endpoints.industry_chains import router as industry_chains_router
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
from ai.errors import (
    AIAnalysisInProgressException,
    AIDisabledException,
    AIImageTooLargeException,
    AIInvalidRequestException,
    AIProviderError,
    AIProviderMisconfiguredException,
    AIProviderUnreachableException,
    AIQuotaExceededException,
    AIRateLimitedException,
    AIStorageUnavailableException,
    AITimeoutException,
)
from industry_chain.errors import (
    IndustryChainCapExceededException,
    IndustryChainConfigInvalidException,
    IndustryChainCrawlInProgressException,
    IndustryChainDisabledException,
    IndustryChainEdgeNotFoundException,
    IndustryChainModelInvalidException,
    IndustryChainNoKeyException,
    IndustryChainNotFoundException,
    IndustryChainStorageUnavailableException,
)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mystock-backend")
logging.getLogger("httpx").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 全市場抓取是行程內的背景執行緒，不會跨行程存活：啟動時若還有 status='running' 的紀錄，
    # 一定是上次行程留下的孤兒。不收掉的話 V10 的部分唯一索引會讓之後所有作業都建不起來，
    # 前端的同步進度也會永遠卡在「進行中」。失敗不阻斷啟動（DATA_SOURCE=json 時本來就沒這張表）。
    try:
        from repositories.market_repository import MarketRepository
        await MarketRepository().reap_orphaned_fetch_jobs()
    except Exception as exc:
        logger.warning("[全市場] 回收殘留抓取作業失敗（已略過）：%s", exc)

    # ── AI 技術分析報告：回收上次行程留下的孤兒 running 列（比照上方全市場抓取的
    #    reap_orphaned_fetch_jobs()，見 docs/16.AI技術分析/AI技術分析規劃.md §5.8）。
    #    僅在 AI_ANALYSIS_ENABLED=true 時嘗試，失敗不阻斷啟動；DATA_SOURCE=json 時本來就沒這幾張表。
    try:
        from ai import config as ai_config
        if ai_config.is_enabled():
            from db.session import get_async_session
            from repositories.ai_report_repository import AIReportRepository
            from repositories.activity_log_repository import ActivityLogRepository
            async with get_async_session() as _ai_session:
                reaped = await AIReportRepository(_ai_session).reap_orphaned(ai_config.get_stuck_timeout_min())
                if reaped:
                    await ActivityLogRepository(_ai_session).log(
                        "AI_REPORT_REAP", success=True, comments=f"回收 {reaped} 筆孤兒 running 列"
                    )
                await _ai_session.commit()
            if reaped:
                logger.info("[AI] 回收孤兒 running 報告列 %d 筆", reaped)
    except Exception as exc:
        logger.warning("[AI] 回收殘留執行紀錄失敗（已略過）：%s", exc)

    scheduler = create_scheduler()
    scheduler.start()
    asyncio.create_task(run_startup_backfill())  # 背景執行，缺漏回補不阻塞服務啟動（見 phase3_5 設計文件第 3.1 節）

    # 啟動時自動抓一次每日匯率（USD/JPY/CNY），失敗不阻塞服務啟動（見 services/exchange_rate_fetcher.py）
    from services.exchange_rate_fetcher import fetch_exchange_rates_startup
    asyncio.create_task(fetch_exchange_rates_startup())

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
app.include_router(markets_router)
app.include_router(market_router)
app.include_router(indices_router)
app.include_router(industry_chains_router)
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
        "error": {"code": "NOTIFY_INVALID_INPUT", "message": str(exc) or "輸入不合法"}
    })

@app.exception_handler(PreferenceWideningException)
async def notify_widening_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False,
        "error": {"code": "NOTIFY_SCOPE_WIDENING", "message": str(exc) or "不得放寬授權範圍"}
    })

@app.exception_handler(ChannelUnavailableException)
async def notify_channel_unavailable_handler(request, exc):
    return JSONResponse(status_code=409, content={
        "success": False,
        "error": {"code": "NOTIFY_CHANNEL_UNAVAILABLE", "message": str(exc) or "管道目前無法使用"}
    })

# ── AI 技術分析報告例外處理（規格書 §4.7）─────────────────────────────────
@app.exception_handler(AIDisabledException)
async def ai_disabled_handler(request, exc):
    return JSONResponse(status_code=403, content={
        "success": False, "error": {"code": "AI_DISABLED", "message": str(exc) or "AI 技術分析報告功能未啟用"}
    })

@app.exception_handler(AIStorageUnavailableException)
async def ai_storage_unavailable_handler(request, exc):
    return JSONResponse(status_code=503, content={
        "success": False, "error": {"code": "AI_STORAGE_UNAVAILABLE", "message": str(exc) or "AI 報告資料庫目前無法使用"}
    })

@app.exception_handler(AIQuotaExceededException)
async def ai_quota_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={
        "success": False, "error": {"code": "AI_QUOTA_EXCEEDED", "message": str(exc) or "今日新報告數已達上限"}
    })

@app.exception_handler(AIAnalysisInProgressException)
async def ai_in_progress_handler(request, exc):
    return JSONResponse(status_code=409, content={
        "success": False, "error": {"code": "AI_ANALYSIS_IN_PROGRESS", "message": str(exc) or "分析正在進行中"}
    })

@app.exception_handler(AIProviderMisconfiguredException)
async def ai_misconfigured_handler(request, exc):
    return JSONResponse(status_code=500, content={
        "success": False, "error": {"code": "AI_PROVIDER_MISCONFIGURED", "message": "AI Provider 設定有誤，請檢查 .env"}
    })

@app.exception_handler(AIRateLimitedException)
async def ai_rate_limited_handler(request, exc):
    headers = {"Retry-After": str(exc.retry_after_sec)} if getattr(exc, "retry_after_sec", None) else None
    return JSONResponse(status_code=429, headers=headers, content={
        "success": False, "error": {"code": "AI_RATE_LIMITED", "message": str(exc) or "已達 LLM 服務限流上限"}
    })

@app.exception_handler(AITimeoutException)
async def ai_timeout_handler(request, exc):
    return JSONResponse(status_code=504, content={
        "success": False, "error": {"code": "AI_TIMEOUT", "message": str(exc) or "呼叫 LLM 逾時"}
    })

@app.exception_handler(AIProviderUnreachableException)
async def ai_unreachable_handler(request, exc):
    return JSONResponse(status_code=502, content={
        "success": False, "error": {"code": "AI_PROVIDER_UNREACHABLE", "message": str(exc) or "無法連線至 LLM 服務"}
    })

@app.exception_handler(AIProviderError)
async def ai_provider_error_handler(request, exc):
    return JSONResponse(status_code=502, content={
        "success": False, "error": {"code": "AI_PROVIDER_ERROR", "message": str(exc) or "LLM 服務發生未知錯誤"}
    })

@app.exception_handler(AIInvalidRequestException)
async def ai_invalid_request_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False, "error": {"code": "AI_INVALID_REQUEST", "message": str(exc) or "請求參數不合法"}
    })

@app.exception_handler(AIImageTooLargeException)
async def ai_image_too_large_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False, "error": {"code": "AI_IMAGE_TOO_LARGE", "message": str(exc) or "圖片超過大小上限"}
    })

# ── 產業鏈知識圖譜例外處理（規格書 §7）─────────────────────────────────
@app.exception_handler(IndustryChainDisabledException)
async def ic_disabled_handler(request, exc):
    return JSONResponse(status_code=403, content={
        "success": False, "error": {"code": "IC_DISABLED", "message": str(exc) or "產業鏈知識圖譜功能未啟用"}
    })

@app.exception_handler(IndustryChainStorageUnavailableException)
async def ic_storage_unavailable_handler(request, exc):
    return JSONResponse(status_code=503, content={
        "success": False, "error": {"code": "IC_STORAGE_UNAVAILABLE", "message": str(exc) or "產業鏈資料庫目前無法使用"}
    })

@app.exception_handler(IndustryChainNotFoundException)
async def ic_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False, "error": {"code": "IC_CHAIN_NOT_FOUND", "message": str(exc) or "找不到產業鏈"}
    })

@app.exception_handler(IndustryChainEdgeNotFoundException)
async def ic_edge_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False, "error": {"code": "IC_EDGE_NOT_FOUND", "message": str(exc) or "找不到指定的邊"}
    })

@app.exception_handler(IndustryChainCrawlInProgressException)
async def ic_crawl_in_progress_handler(request, exc):
    return JSONResponse(status_code=409, content={
        "success": False, "error": {"code": "IC_CRAWL_IN_PROGRESS", "message": str(exc) or "已有產業鏈萃取工作執行中"}
    })

@app.exception_handler(IndustryChainCapExceededException)
async def ic_cap_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={
        "success": False, "error": {"code": "IC_LLM_CAP_HIT", "message": str(exc) or "本月萃取呼叫已達上限"}
    })

@app.exception_handler(IndustryChainModelInvalidException)
async def ic_model_invalid_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False, "error": {"code": "IC_LLM_MODEL_INVALID", "message": str(exc) or "模型不在白名單內"}
    })

@app.exception_handler(IndustryChainNoKeyException)
async def ic_no_key_handler(request, exc):
    return JSONResponse(status_code=500, content={
        "success": False, "error": {"code": "IC_LLM_NO_KEY", "message": str(exc) or "API 金鑰未設定"}
    })

@app.exception_handler(IndustryChainConfigInvalidException)
async def ic_config_invalid_handler(request, exc):
    return JSONResponse(status_code=400, content={
        "success": False, "error": {"code": "IC_CONFIG_INVALID", "message": str(exc) or "骨架設定未通過驗證"}
    })

@app.get("/health", summary="健康檢查端點", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "MyStock Backend API"}

if __name__ == "__main__":
    print("=" * 60)
    print("MyStock 股市分析 FastAPI 後端服務啟動中...")
    print("API 文件請開啟: http://localhost:8000/docs")
    print("=" * 60)
    # reload 預設關閉：--reload 會多開一個 watcher 子行程，開發過程反覆重啟容易留下卡在
    # port 8000 的殘留行程（見 stop_servers.bat）。需要熱重載時設 UVICORN_RELOAD=true。
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=reload_enabled)
