"""應用程式設定"""
import os
import sys

# 載入 .env（python-dotenv 安裝後生效，否則略過）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_resource_path(relative_path: str) -> str:
    """PyInstaller 打包後路徑處理：開發時回傳相對路徑，打包後回傳 _MEIPASS 路徑"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ── Telegram Bot 設定 ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# 重量上限（超過需主管授權）
WEIGHT_LIMIT = 5000

# 伺服器設定
HOST = "0.0.0.0"
PORT = 8001

# CORS 設定
CORS_ORIGINS = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:8001",   # FastAPI self
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8001",
]
