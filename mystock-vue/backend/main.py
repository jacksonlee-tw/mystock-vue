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
from api.v1.endpoints.markets import router as markets_router
from api.v1.endpoints.alerts import router as alerts_router
from api.v1.endpoints.strategies import router as strategies_router
from api.v1.endpoints.fundamentals import router as fundamentals_router
from core.exceptions import SymbolNotFoundException
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
app.include_router(alerts_router)
app.include_router(strategies_router)
app.include_router(fundamentals_router)

@app.exception_handler(SymbolNotFoundException)
async def symbol_not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={
        "success": False,
        "error": {"code": "SYMBOL_NOT_FOUND", "message": str(exc)}
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
