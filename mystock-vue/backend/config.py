import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# 載入 .env
load_dotenv(ENV_PATH)

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
DEFAULT_MARKET_FETCH_THROTTLE_SECONDS = 3
DEFAULT_MARKET_MANUAL_BACKFILL_MAX_DAYS = 120
DEFAULT_MARKET_FETCH_ENABLED = True
DEFAULT_UNIVERSE_TIER = "all_tracked"
# 抓歷史資料的上限（月）。目前系統實際累積的資料量遠低於此，等同於「抓全部歷史」；
# 之所以不用 None／不限制，是沿用 aggregate_stock_data() 既有的 months 參數介面。
# 集中放在這裡（而非各自散在 services/chip_provider.py、services/stock_service.py）是因為
# 兩處都要用同一個值：KD 暖身切片（KD指標 設計規格書 §6.3）要求「先以完整歷史計算，再依
# 顯示區間切片」，兩處若各自寫一個常數、之後改了忘記同步，切片基準就會跟策略引擎對不起來。
MAX_HISTORY_MONTHS = 60

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
    """追蹤清單（爬蟲抓取範圍）的唯一資料來源：Postgres `portfolio_watchlist`
    （`is_crawl_enabled = TRUE`）。2026-08-30 起不再讀寫 `.env` 的 `STOCK_CODES`/`US_STOCK_CODES`
    （撤回 ADR-02「`.env` 為鏡像」設計，見 docs/15.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md）；
    此後追蹤清單管理一律要求 Postgres 可連線，不再有 JSON-only 部署下的降級路徑。

    只能在「目前沒有執行中事件迴圈」的同步呼叫端使用（爬蟲／背景任務／腳本）——內部用
    asyncio.run() 橋接，會在既有事件迴圈中直接丟出 RuntimeError。已在事件迴圈內的呼叫端
    （FastAPI async 端點、async service 函式）請改用
    `services.tracking_service.get_crawl_enabled_symbols()`（await）。"""
    from repositories.portfolio_repository import list_crawl_enabled_symbols_sync
    return list_crawl_enabled_symbols_sync(market)

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

def get_market_fetch_throttle_seconds() -> int:
    """全市場爬蟲請求節流秒數（選股功能與爬蟲 規格書 §3.1-7）。"""
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("MARKET_FETCH_THROTTLE_SECONDS", str(DEFAULT_MARKET_FETCH_THROTTLE_SECONDS)))
    except ValueError:
        return DEFAULT_MARKET_FETCH_THROTTLE_SECONDS

def get_market_manual_backfill_max_days() -> int:
    """全市場手動回補單次上限天數（選股功能與爬蟲 規格書 §3.9.6）。"""
    load_dotenv(ENV_PATH, override=True)
    try:
        return int(os.getenv("MARKET_MANUAL_BACKFILL_MAX_DAYS", str(DEFAULT_MARKET_MANUAL_BACKFILL_MAX_DAYS)))
    except ValueError:
        return DEFAULT_MARKET_MANUAL_BACKFILL_MAX_DAYS

def is_market_fetch_enabled() -> bool:
    """全市場每日抓取排程是否啟用。"""
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("MARKET_FETCH_ENABLED", "true").strip().lower() != "false"

def get_default_universe_tier() -> str:
    """選股池預設層級（選股功能與爬蟲 規格書 §7）。"""
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("DEFAULT_UNIVERSE_TIER", DEFAULT_UNIVERSE_TIER).strip()



# ── 排程設定 ──────────────────────────────────────────────────────────────

def _set_env_values(pairs: dict[str, str]) -> None:
    """一次寫入多個 .env 設定值（找到既有鍵就地覆寫、找不到就附加，只讀寫檔案一次）。

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
