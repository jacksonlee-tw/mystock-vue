import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# 載入 .env
load_dotenv(ENV_PATH)

DEFAULT_STOCKS = ["0050", "2330", "006208", "2317"]
DEFAULT_US_STOCKS = ["AAPL", "MSFT", "GOOGL", "TSLA"]
DEFAULT_MONTHS_RANGE = 3
DEFAULT_QUARTERS_RANGE = 4
ENABLED_MARKETS_DEFAULT = ["tw", "us"]
DEFAULT_DATA_SOURCE = "json"
VALID_DATA_SOURCES = ("json", "postgres")
DEFAULT_BACKFILL_MAX_DAYS = 90
DEFAULT_STRATEGY_CONFIG_PATH = os.path.join(BASE_DIR, "strategy_config", "strategies.yaml")
DEFAULT_ALERT_COOLDOWN_DAYS = 1
DEFAULT_INDEX_CONFIG_PATH = os.path.join(BASE_DIR, "index_config", "indices.yaml")
DEFAULT_INDEX_HISTORY_YEARS = 5

# ── 每日抓取＋掃描排程（見 services/scheduler.py）─────────────────────────
# 時間一律以 SCHEDULE_TIMEZONE 解讀；台股盤後 14:30、美股收盤後隔日台北時間 06:00。
DEFAULT_SCHEDULE_TIMEZONE = "Asia/Taipei"
DEFAULT_SCHEDULE_TIMES = {"tw": "14:30", "us": "06:00"}

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "*"
]

def get_target_stocks(market: str = "tw") -> list[str]:
    load_dotenv(ENV_PATH, override=True)
    if market == "us":
        raw = os.getenv("US_STOCK_CODES", "")
        stocks = [s.strip() for s in raw.split(",") if s.strip()]
        return stocks or DEFAULT_US_STOCKS
    else:
        raw = os.getenv("STOCK_CODES", "")
        stocks = [s.strip() for s in raw.split(",") if s.strip()]
        return stocks or DEFAULT_STOCKS

def save_target_stocks(stocks: list[str], market: str = "tw") -> None:
    unique_stocks = list(dict.fromkeys(stocks))
    raw = ",".join(unique_stocks)
    env_key = "US_STOCK_CODES" if market == "us" else "STOCK_CODES"
    
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_key}="):
            lines[i] = f"{env_key}={raw}\n"
            found = True
            break
            
    if not found:
        lines.append(f"{env_key}={raw}\n")
        
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    os.environ[env_key] = raw

def get_enabled_markets() -> list[str]:
    load_dotenv(ENV_PATH, override=True)
    raw = os.getenv("ENABLED_MARKETS", "")
    markets = [m.strip().lower() for m in raw.split(",") if m.strip()]
    return markets or ENABLED_MARKETS_DEFAULT

def get_months_range() -> int:
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("MONTHS_RANGE", str(DEFAULT_MONTHS_RANGE)))
    except ValueError:
        return DEFAULT_MONTHS_RANGE

def get_quarters_range() -> int:
    """季報 EPS 回溯抓取的季數（見 services/mops_eps_fetcher.py）。"""
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("QUARTERS_RANGE", str(DEFAULT_QUARTERS_RANGE)))
    except ValueError:
        return DEFAULT_QUARTERS_RANGE

def get_data_source() -> str:
    load_dotenv(ENV_PATH, override=True)
    source = os.getenv("DATA_SOURCE", DEFAULT_DATA_SOURCE).strip().lower()
    # 辨識不了的值一律退回 json（現行可用架構），設定打錯字不該讓服務起不來
    return source if source in VALID_DATA_SOURCES else DEFAULT_DATA_SOURCE

def get_backfill_max_days() -> int:
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("BACKFILL_MAX_DAYS", str(DEFAULT_BACKFILL_MAX_DAYS)))
    except ValueError:
        return DEFAULT_BACKFILL_MAX_DAYS

def get_strategy_config_path() -> str:
    """策略設定檔（YAML）路徑，見策略管理架構 設計文件第 8 節 STRATEGY_CONFIG_PATH。"""
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("STRATEGY_CONFIG_PATH", DEFAULT_STRATEGY_CONFIG_PATH)

def get_alert_cooldown_days() -> int:
    """訊號去重（Cooldown）天數，見策略管理架構 設計文件第 8 節 ALERT_COOLDOWN_DAYS。"""
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("ALERT_COOLDOWN_DAYS", str(DEFAULT_ALERT_COOLDOWN_DAYS)))
    except ValueError:
        return DEFAULT_ALERT_COOLDOWN_DAYS

def get_index_config_path() -> str:
    """指數定義檔（YAML）路徑，見大盤指數功能規劃書第 4.1 節。"""
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("INDEX_CONFIG_PATH", DEFAULT_INDEX_CONFIG_PATH)

def get_index_history_years() -> int:
    """歷史回補預設年數，供 scripts/init_index_history.py 使用（大盤指數功能規劃書第 3.3 節）。"""
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("INDEX_HISTORY_YEARS", str(DEFAULT_INDEX_HISTORY_YEARS)))
    except ValueError:
        return DEFAULT_INDEX_HISTORY_YEARS


# ── 排程設定 ──────────────────────────────────────────────────────────────

def _set_env_values(pairs: dict[str, str]) -> None:
    """一次寫入多個 .env 設定值（比照 save_target_stocks 的寫法，但只讀寫檔案一次）。

    排程是「一組」設定，逐鍵各自 rewrite 檔案會讓中途失敗留下半套狀態。
    """
    lines: list[str] = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    for key, value in pairs.items():
        replacement = f"{key}={value}\n"
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = replacement
                break
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(replacement)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    for key, value in pairs.items():
        os.environ[key] = value


def parse_schedule_time(raw: str) -> tuple[int, int]:
    """把 "HH:MM" 解析成 (hour, minute)；格式或範圍不對就丟 ValueError。"""
    parts = str(raw).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"排程時間格式須為 HH:MM，收到：{raw}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"排程時間超出範圍（00:00–23:59），收到：{raw}")
    return hour, minute


def get_schedule_timezone() -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("SCHEDULE_TIMEZONE", DEFAULT_SCHEDULE_TIMEZONE).strip() or DEFAULT_SCHEDULE_TIMEZONE


def get_schedule_config() -> dict:
    """每日抓取排程設定。設定值壞掉時退回預設值，不讓排程整個起不來
    （比照 get_data_source() 對無法辨識值的處理）。"""
    load_dotenv(ENV_PATH, override=True)

    markets = {}
    for market, default_time in DEFAULT_SCHEDULE_TIMES.items():
        raw_time = os.getenv(f"{market.upper()}_SCHEDULE_TIME", default_time)
        try:
            hour, minute = parse_schedule_time(raw_time)
        except ValueError:
            hour, minute = parse_schedule_time(default_time)
            raw_time = default_time
        enabled = os.getenv(f"{market.upper()}_SCHEDULE_ENABLED", "true").strip().lower() != "false"
        markets[market] = {"time": f"{hour:02d}:{minute:02d}", "hour": hour, "minute": minute, "enabled": enabled}

    return {"timezone": get_schedule_timezone(), "markets": markets}


def save_schedule_config(markets: dict) -> dict:
    """寫回 .env 並回傳存檔後的設定。markets 形如
    {"tw": {"time": "14:30", "enabled": True}, "us": {...}}；未提供的市場維持原值。"""
    current = get_schedule_config()["markets"]

    pairs: dict[str, str] = {}
    for market, patch in markets.items():
        if market not in DEFAULT_SCHEDULE_TIMES:
            raise ValueError(f"不支援的市場：{market}")
        if "time" in patch and patch["time"] is not None:
            hour, minute = parse_schedule_time(patch["time"])  # 格式錯誤在此擋下，不會寫入檔案
            pairs[f"{market.upper()}_SCHEDULE_TIME"] = f"{hour:02d}:{minute:02d}"
        if "enabled" in patch and patch["enabled"] is not None:
            pairs[f"{market.upper()}_SCHEDULE_ENABLED"] = "true" if patch["enabled"] else "false"

    if pairs:
        _set_env_values(pairs)
    return get_schedule_config() if pairs else {"timezone": get_schedule_timezone(), "markets": current}
