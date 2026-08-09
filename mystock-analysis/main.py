import logging
import multiprocessing
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dishka.integrations.fastapi import setup_dishka

from backend.core.config import CORS_ORIGINS, HOST, PORT, get_resource_path
from backend.core import handlers
from backend.core.container import create_container
from backend.api.v1.endpoints import entry, exit, ticket, websocket, db_status, po, auth, trucks, warnlog, trace, telegram, gold
from backend.db.session import check_availability

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)

# ── FastAPI 應用程式 ──────────────────────────────────────────────────────

app = FastAPI(title="MyStock 選股分析系統")

# ── CORS 設定（開發時允許 Vite dev server 跨域存取）─────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全域例外處理（AppException → 標準 JSON 回應）─────────────────────────

handlers.register(app)

# ── 應用程式啟動：檢查 DB 可用性 ─────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    ok = check_availability()
    mode = "MS SQL Server" if ok else "記憶體 Mock"
    log.info("🚀 過磅作業系統啟動 — 資料庫模式：%s", mode)


@app.on_event("shutdown")
async def on_shutdown():
    from backend.db.engine import dispose_engine
    dispose_engine()

# ── Dishka DI 容器 ───────────────────────────────────────────────────────

container = create_container()
setup_dishka(container, app)

# ── 註冊路由 ──────────────────────────────────────────────────────────────

app.include_router(entry.router)
app.include_router(exit.router)
app.include_router(ticket.router)
app.include_router(db_status.router)
app.include_router(po.router)
app.include_router(auth.router)
app.include_router(trucks.router)
app.include_router(warnlog.router)
app.include_router(trace.router)
app.include_router(telegram.router)
app.include_router(gold.router)
app.include_router(websocket.router)

# ── 靜態前端（必須置於所有 API 路由之後）─────────────────────────────────

static_dir = get_resource_path("static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

# ── 啟動入口 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    multiprocessing.freeze_support()

    print("=" * 50)
    print("⚖️  過磅作業系統啟動中...")
    print(f"🌐  請在瀏覽器開啟: http://localhost:{PORT}")
    print("按 Ctrl+C 停止伺服器")
    print("=" * 50)

    if getattr(sys, 'frozen', False):
        uvicorn.run(app, host=HOST, port=PORT, reload=False, workers=1)
    else:
        uvicorn.run("main:app", host=HOST, port=PORT, reload=True, workers=1)
