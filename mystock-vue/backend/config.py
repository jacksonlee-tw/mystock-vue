import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# 載入 .env
load_dotenv(ENV_PATH)

DEFAULT_STOCKS = ["0050", "2330", "006208", "2317"]
DEFAULT_MONTHS_RANGE = 3

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "*"
]

def get_target_stocks() -> list[str]:
    load_dotenv(ENV_PATH, override=True)
    raw = os.getenv("STOCK_CODES", "")
    stocks = [s.strip() for s in raw.split(",") if s.strip()]
    return stocks or DEFAULT_STOCKS

def save_target_stocks(stocks: list[str]) -> None:
    unique_stocks = list(dict.fromkeys(stocks))
    raw = ",".join(unique_stocks)
    
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    found = False
    for i, line in enumerate(lines):
        if line.startswith("STOCK_CODES="):
            lines[i] = f"STOCK_CODES={raw}\n"
            found = True
            break
            
    if not found:
        lines.append(f"STOCK_CODES={raw}\n")
        
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    os.environ["STOCK_CODES"] = raw

def get_months_range() -> int:
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("MONTHS_RANGE", str(DEFAULT_MONTHS_RANGE)))
    except ValueError:
        return DEFAULT_MONTHS_RANGE
