import logging
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from api.v1.endpoints.stocks import router as stocks_router
from api.v1.endpoints.fetch import router as fetch_router
from api.v1.endpoints.markets import router as markets_router
from core.exceptions import SymbolNotFoundException
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mystock-backend")

app = FastAPI(
    title="MyStock 股市三大法人與籌碼分析 API 服務",
    description="提供台灣股市三大法人買賣超、融資融券、K線圖歷史數據聚合與 TWSE 自動抓取服務",
    version="1.0.0"
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
