import os
import json
import calendar
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import threading

from config import DATA_DIR, BASE_DIR, get_target_stocks, get_months_range, get_twse_rate_settings
from db.dual_write import dual_write_daily_data, dual_write_no_trading_days, log_crawler_run
from services.twse_client import get_twse_limiter, twse_get_json

logger = logging.getLogger("mystock-backend")

# ── 抓取進度狀態管理類別 ─────────────────────────────────────────

class FetchStatusManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.is_running = False
        self.total_steps = 100
        self.current_step = 0
        self.progress_percent = 0
        self.message = "靜止中"
        self.status = "idle"  # idle, running, completed, error
        self.logs: List[str] = []
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None
        self.error: Optional[str] = None

    def start(self, message: str = "開始抓取 TWSE 資料..."):
        with self._lock:
            self.is_running = True
            self.total_steps = 100
            self.current_step = 0
            self.progress_percent = 0
            self.message = message
            self.status = "running"
            self.logs = [f"[{datetime.now().strftime('%H:%M:%S')}] {message}"]
            self.started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.finished_at = None
            self.error = None

    def update(self, current_step: int, total_steps: int, message: str):
        with self._lock:
            self.current_step = current_step
            self.total_steps = max(1, total_steps)
            self.progress_percent = min(100, int((current_step / self.total_steps) * 100))
            self.message = message
            log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
            self.logs.append(log_entry)

    def complete(self, message: str = "資料抓取完成！"):
        with self._lock:
            self.is_running = False
            self.current_step = self.total_steps
            self.progress_percent = 100
            self.message = message
            self.status = "completed"
            self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
            self.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def fail(self, error_msg: str):
        with self._lock:
            self.is_running = False
            self.status = "error"
            self.error = error_msg
            self.message = f"抓取失敗: {error_msg}"
            self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 錯誤: {error_msg}")
            self.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_running": self.is_running,
                "progress_percent": self.progress_percent,
                "current_step": self.current_step,
                "total_steps": self.total_steps,
                "message": self.message,
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "error": self.error,
                "logs": self.logs[-50:]  # 最近 50 條 log
            }

fetch_status = FetchStatusManager()

# TWSE 請求（Session、重試、跨執行緒共用的自適應限流）集中在 services/twse_client.py，見該檔說明。

# ── 輔助函式 ──────────────────────────────────────────────────

from markets.tw import FIELD_MAP

# 舊資料檔可能殘留中文 key（load_stock_json 會轉成英文，但寫入端曾以中文落檔）
_ALT_KEYS = {v: k for k, v in FIELD_MAP.items()}

# 價格類欄位：抓不到行情時絕不可用 0 覆蓋既有值
_PRICE_FIELDS = {
    "開盤價", "最高價", "最低價", "收盤價",
    "成交股數(股)", "成交金額(元)", "成交筆數(筆)", "估算買賣超金額(萬元)",
}

def _field(record: dict, en_key: str, default=None):
    """讀取記錄欄位，同時容忍英文與中文 key。"""
    value = record.get(en_key)
    if value is not None:
        return value
    return record.get(_ALT_KEYS.get(en_key, en_key), default)

def _normalize_keys(record: dict) -> dict:
    """落檔前把中文 key 轉成英文，避免同一筆記錄中英文 key 並存。"""
    return {FIELD_MAP.get(k, k): v for k, v in record.items()}

def stock_json_path(stock_id: str, market: str = "tw") -> str:
    market_dir = os.path.join(DATA_DIR, market)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{stock_id}.json")

def load_stock_json(stock_id: str, market: str = "tw") -> dict:
    path = stock_json_path(stock_id, market)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Normalize Chinese keys to English keys
        if market == "tw":
            for date_key, record in data.items():
                new_record = {}
                for k, v in record.items():
                    if k in FIELD_MAP:
                        new_record[FIELD_MAP[k]] = v
                    else:
                        new_record[k] = v
                data[date_key] = new_record
                
        return data
    except Exception:
        return {}

NO_TRADING_DAYS_FILE = os.path.join(DATA_DIR, "_no_trading_days.json")

def load_no_trading_days() -> set:
    if not os.path.exists(NO_TRADING_DAYS_FILE):
        return set()
    try:
        with open(NO_TRADING_DAYS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_no_trading_days(days: set) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NO_TRADING_DAYS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(days), f, ensure_ascii=False, indent=2)

def months_ago(months: int, from_date: Optional[datetime] = None) -> datetime:
    base = from_date or datetime.now()
    month_index = base.month - 1 - months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)

def _months_in_range(days: int) -> list:
    today = datetime.now()
    start = today - timedelta(days=days - 1)
    months = []
    cursor = start.replace(day=1)
    while cursor <= today:
        months.append((cursor.year, cursor.month))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months

def _parse_quote_field(row: list, index: int, cast):
    try:
        return cast(str(row[index]).replace(",", ""))
    except (ValueError, IndexError, TypeError):
        return None

# ── 全市場行情（MI_INDEX，取代逐檔逐月 STOCK_DAY）─────────────────────
# 舊版逐檔呼叫 STOCK_DAY（單檔單月），請求量 = 追蹤股票數 × 月數，股票追蹤清單一長就
# 線性變慢。MI_INDEX 是「單日全市場」端點，一次請求就能拿到當天所有股票的 OHLCV，
# 因此改成比照 fetch_stock_institutional_data() 逐日抓取，請求量從此只跟天數成正比，
# 與追蹤股票數無關。欄位定位邏輯與 market_fetcher.py（選股功能全市場管線）的
# fetch_twse_quotes() 一致，該處已實測驗證過（見 docs/05.籌碼選股策略/籌碼選股.md）。
_MI_INDEX_FIELD_RULES = [
    ("開盤價", "開盤價", float),
    ("最高價", "最高價", float),
    ("最低價", "最低價", float),
    ("收盤價", "收盤價", float),
    ("成交股數(股)", "成交股數", int),
    ("成交金額(元)", "成交金額", int),
    ("成交筆數(筆)", "成交筆數", int),
]

def _locate_mi_index_quote_table(res: dict) -> Optional[dict]:
    """MI_INDEX 一次回應含多張表格，需找出「每日收盤行情」那張。"""
    for t in res.get("tables", []):
        title = t.get("title", "")
        if "每日收盤行情" in title or "價格資訊" in title or len(t.get("data", [])) > 500:
            return t
    if "data9" in res:
        return {"fields": res.get("fields9", []), "data": res.get("data9", [])}
    return None

def _locate_mi_index_columns(fields: list) -> Optional[dict]:
    """依 fields 標頭動態定位欄位索引（欄位順序不像 STOCK_DAY 固定）。
    找不到「證券代號」或「收盤價」代表表格不符預期，回傳 None 由呼叫端整批放棄，
    絕不用猜的索引落檔（比照 _locate_t86_columns 的原則）。"""
    if not fields:
        return None
    col_map = {}
    for i, f in enumerate(fields):
        if "證券代號" in f and "symbol" not in col_map:
            col_map["symbol"] = i
    for out_field, keyword, _cast in _MI_INDEX_FIELD_RULES:
        idx = next((i for i, f in enumerate(fields) if keyword in f), None)
        if idx is not None:
            col_map[out_field] = idx
    if "symbol" not in col_map or "收盤價" not in col_map:
        return None
    return col_map

def fetch_mi_index_quotes(date_key: str, target_stocks: set):
    """抓取單一交易日的全市場行情，僅保留 target_stocks 需要的部分。
    回傳 (quotes_by_stock, is_holiday)；quotes_by_stock 的 value 與舊版
    fetch_daily_quotes() 回傳形狀相同（中文 key），供既有呼叫端無痛沿用。"""
    date_str = date_key.replace("-", "")
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALLBUT0999&response=json"
    try:
        res = twse_get_json(url)
    except Exception as e:
        logger.warning(f"[MI_INDEX] {date_key} 抓取失敗: {e}")
        return {}, False

    stat = res.get("stat", "")
    if stat != "OK":
        return {}, ("非交易日" in stat or "查無" in stat)

    table = _locate_mi_index_quote_table(res)
    if not table:
        return {}, False

    col_map = _locate_mi_index_columns(table.get("fields", []))
    if col_map is None:
        logger.error(f"[MI_INDEX] {date_key} 欄位定位失敗，本日不落檔行情（欄位: {table.get('fields')}）")
        return {}, False

    quotes = {}
    for row in table.get("data", []):
        sym_idx = col_map["symbol"]
        if len(row) <= sym_idx:
            continue
        stock_id = str(row[sym_idx]).strip()
        if stock_id not in target_stocks:
            continue
        close = _parse_quote_field(row, col_map["收盤價"], float)
        if close is None:
            continue
        quote = {"收盤價": close}
        for out_field, _keyword, cast in _MI_INDEX_FIELD_RULES:
            if out_field == "收盤價":
                continue
            idx = col_map.get(out_field)
            value = _parse_quote_field(row, idx, cast) if idx is not None else None
            quote[out_field] = value if value is not None else cast(0)
        quotes[stock_id] = quote

    return quotes, False

def backfill_daily_quotes(target_stocks: list, quote_lookup: dict) -> int:
    patched = 0
    for stock_id in target_stocks:
        stock_data = load_stock_json(stock_id) or {}
        changed = False
        patched_dates = set()

        quotes_for_stock = quote_lookup.get(stock_id, {})
        for date_key, quote in quotes_for_stock.items():
            if date_key not in stock_data:
                # Add entirely new entry for today's price (even if no institutional data yet)
                stock_data[date_key] = _normalize_keys(quote)
                changed = True
                patched += 1
                patched_dates.add(date_key)
            else:
                record = stock_data[date_key]
                # 已有非零收盤價代表這天完好；價格為 0 或缺漏才需要修補
                if _field(record, "close", 0):
                    continue
                record.update(_normalize_keys(quote))
                total_lots = _field(record, "institutional_total", 0)
                if total_lots and quote.get("收盤價"):
                    record["institutional_amount_est"] = round(total_lots * quote["收盤價"] / 10, 2)
                changed = True
                patched += 1
                patched_dates.add(date_key)

        if changed:
            stock_data = {k: _normalize_keys(v) for k, v in stock_data.items()}
            with open(stock_json_path(stock_id), "w", encoding="utf-8") as f:
                # Sort by date before dumping
                sorted_data = dict(sorted(stock_data.items()))
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)
            dual_write_daily_data(stock_id, "tw", {d: stock_data[d] for d in patched_dates if d in stock_data})

    return patched

_MI_MARGN_FIELD_MAP = {
    "融資買進(張)": 2, "融資賣出(張)": 3, "融資現金償還(張)": 4,
    "融資前日餘額(張)": 5, "融資餘額(張)": 6,
    "融券買進(張)": 8, "融券賣出(張)": 9, "融券現券償還(張)": 10,
    "融券前日餘額(張)": 11, "融券餘額(張)": 12,
    "資券互抵(張)": 14,
}

def _parse_margin_row(row: list):
    try:
        return {field: int(row[index].replace(",", "").strip()) for field, index in _MI_MARGN_FIELD_MAP.items()}
    except (ValueError, IndexError, AttributeError):
        return None

# T86「selectType=ALL」實際回傳 19 欄，且欄位順序不保證跨時間穩定（籌碼選股策略
# 設計文件第 1.2 節 P0 缺陷：舊碼寫死索引 4/7/10/11，其中 7/10/11 全部錯位——
# 「投信買賣超」誤讀到恆為 0 的「外資自營商」欄、「三大法人合計」誤讀到「自營商合計」）。
# 改為依 fields 標頭動態定位，找不到就整批放棄、絕不用猜的索引落檔。
#
# 每條規則都先要求含「買賣超」，排除掉同一類別下的「買進/賣出」毛額欄位；
# 自營商合計還要排除「外資自營商」「自行買賣」「避險」三種子分類欄位，
# 否則字串比對會撞到 T86 實際存在的「外資自營商買進股數」「自營商買賣超股數(避險)」等欄。
def _is_foreign_excl_net(f: str) -> bool:
    return "買賣超" in f and ("外陸資" in f or (f.startswith("外資") and "自營商" not in f))


def _is_foreign_dealer_net(f: str) -> bool:
    return "買賣超" in f and "外資自營商" in f


def _is_trust_net(f: str) -> bool:
    return "買賣超" in f and "投信" in f


def _is_dealer_total_net(f: str) -> bool:
    return (
        "買賣超" in f and "自營商" in f
        and "外資" not in f and "自行買賣" not in f and "避險" not in f
    )


def _is_institutional_net(f: str) -> bool:
    return "買賣超" in f and "三大法人" in f


_T86_FIELD_RULES = [
    ("foreign_excl_idx", _is_foreign_excl_net),
    ("foreign_dealer_idx", _is_foreign_dealer_net),
    ("trust_idx", _is_trust_net),
    ("dealer_idx", _is_dealer_total_net),
    ("institutional_idx", _is_institutional_net),
]


def _locate_t86_columns(fields: list) -> Optional[dict]:
    """依 T86 回應的 fields 標頭動態定位欄位索引。回傳 None 代表格式不符預期，
    呼叫端必須放棄該次法人數字，不可用寫死索引當備援（設計文件第 1.2 節修正要求 1）。"""
    if not fields:
        return None
    located: dict = {}
    used: set = set()
    for key, match in _T86_FIELD_RULES:
        idx = next((i for i, f in enumerate(fields) if match(f) and i not in used), None)
        if idx is None:
            return None
        located[key] = idx
        used.add(idx)
    return located


def _lots(shares: int) -> int:
    """股 → 張，無條件捨去絕對值。取代舊碼的 `// 1000`（floor division 對負數
    系統性低估賣超，例如 -188,933 股會變成 -189 張而非正確的 -188 張，見設計文件第 1.2 節）。"""
    return int(shares / 1000)

# ── 逐日全市場抓取：行情(MI_INDEX) + 融資券(MI_MARGN) + 三大法人(T86) 合併成單一日期迴圈 ──
# 舊版拆成兩趟（先跑完所有日期的行情，再跑一次所有日期的法人／融資券），同一份日期清單走兩遍、
# 每趟各讀一次全部追蹤股票的 JSON，進度條也因此在 50% 處錯位。三個端點都是「單日全市場」，
# 請求量只跟天數成正比，合併成一天一個任務後：每個交易日恰好 3 個請求、JSON 只讀一次，
# 且「日」是天然的併發單位——實際請求速率由 twse_client 的限流器統一控制，併發只吸收網路延遲。

# 只有這幾種回應才代表「這天真的沒資料（休市）」。舉例：被限流或系統忙碌時 stat 也不是 OK，
# 但那不是休市；誤記進 _no_trading_days 會讓該日之後永遠被略過。
_NO_DATA_STAT_MARKERS = ("很抱歉", "沒有符合", "查無", "非交易日")

# 證交所開休市日曆裡，這兩種名稱是「交易日」而非休市日
_TRADING_DAY_NAME_MARKERS = ("開始交易", "最後交易")

_HOLIDAY_SCHEDULE_URL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&date={year}0101"


def _is_no_data_stat(stat: str) -> bool:
    return any(marker in stat for marker in _NO_DATA_STAT_MARKERS)


def _valid_weekdays(days: int, today: datetime) -> list:
    dates = (today - timedelta(days=i) for i in range(days))
    return [d for d in dates if d.weekday() < 5]


def parse_holiday_dates(rows: list, year: int) -> set:
    """從證交所開休市日曆挑出「休市的平日」。端點對未知年份會回退成今年的資料，
    所以年份不符的列一律丟掉；週末本來就會被平日過濾排除，不必收。"""
    holidays = set()
    for row in rows:
        try:
            date_key, name = row[0], row[1]
            day = datetime.strptime(date_key, "%Y-%m-%d")
        except (ValueError, IndexError, TypeError):
            continue
        if day.year != year or day.weekday() >= 5:
            continue
        if any(marker in name for marker in _TRADING_DAY_NAME_MARKERS):
            continue
        holidays.add(date_key)
    return holidays


def sync_holiday_calendar(days: int, today: Optional[datetime] = None) -> int:
    """開跑前把證交所官方休市日曆灌進 _no_trading_days，避免對每個國定假日都去打三個端點
    才知道休市。純加速用的 best-effort：任何失敗只記警告、回傳 0，退回原本「打了才知道」的行為。
    回傳新增的休市日數。"""
    today = today or datetime.now()
    start = today - timedelta(days=days - 1)
    try:
        holidays = set()
        for year in range(start.year, today.year + 1):
            res = twse_get_json(_HOLIDAY_SCHEDULE_URL.format(year=year))
            if str(res.get("stat", "")).lower() != "ok":
                continue
            holidays |= parse_holiday_dates(res.get("data", []), year)
        holidays = {d for d in holidays if d <= today.strftime("%Y-%m-%d")}
        existing = load_no_trading_days()
        new_days = holidays - existing
        if new_days:
            save_no_trading_days(existing | new_days)
            dual_write_no_trading_days("tw", new_days, source="calendar")
        return len(new_days)
    except Exception as e:
        logger.warning(f"[TWSE] 休市日曆同步失敗（不影響抓取，僅少了預先略過假日）: {e}")
        return 0


def _fetch_margin_by_stock(date_str: str, target_set: set) -> dict:
    url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
    try:
        res = twse_get_json(url)
    except Exception as e:
        logger.warning(f"[MI_MARGN] {date_str} 抓取失敗: {e}")
        return {}
    if res.get("stat") != "OK":
        return {}
    tables = res.get("tables", [])
    stock_rows = tables[1].get("data", []) if len(tables) > 1 else []
    margin_by_stock = {}
    for row in stock_rows:
        row_stock_id = row[0].strip()
        if row_stock_id in target_set:
            parsed = _parse_margin_row(row)
            if parsed is not None:
                margin_by_stock[row_stock_id] = parsed
    return margin_by_stock


def _build_institutional_records(res_t86: dict, date_key: str, target_set: set,
                                 day_quotes: dict, margin_by_stock: dict) -> list:
    """把一天的 T86 回應 + 同日行情 + 同日融資券組成寫檔用的記錄（中文 key，供 save_data_to_json 使用）。"""
    columns = _locate_t86_columns(res_t86.get("fields", []))
    if columns is None:
        logger.error(f"[T86] {date_key} 欄位定位失敗，本日不落檔法人數字（欄位: {res_t86.get('fields')}）")

    records = []
    for row in res_t86.get("data", []):
        stock_id = row[0].strip()
        stock_name = row[1].strip()
        if stock_id not in target_set:
            continue

        quote = day_quotes.get(stock_id, {})
        record = {
            "日期": date_key,
            "股票代號": stock_id,
            "股票名稱": stock_name,
        }
        total_lots = None  # 供下方「估算買賣超金額」使用；欄位定位失敗時保持 None
        if columns is not None:
            try:
                foreign_lots = _lots(
                    int(row[columns["foreign_excl_idx"]].replace(",", ""))
                    + int(row[columns["foreign_dealer_idx"]].replace(",", ""))
                )
                trust_lots = _lots(int(row[columns["trust_idx"]].replace(",", "")))
                dealer_lots = _lots(int(row[columns["dealer_idx"]].replace(",", "")))
                total_lots = _lots(int(row[columns["institutional_idx"]].replace(",", "")))
            except (ValueError, IndexError):
                foreign_lots = trust_lots = dealer_lots = total_lots = None

            if total_lots is not None:
                if foreign_lots + trust_lots + dealer_lots != total_lots:
                    logger.debug(
                        f"[T86] {date_key} {stock_id} 法人合計對不上（"
                        f"{foreign_lots}+{trust_lots}+{dealer_lots} != {total_lots}），"
                        "張數四捨五入誤差，僅記錄不阻斷"
                    )
                record.update({
                    "外資買賣超(張)": foreign_lots,
                    "投信買賣超(張)": trust_lots,
                    "自營商買賣超(張)": dealer_lots,
                    "合計買賣超(張)": total_lots,
                })
        # 只有真的抓到行情才寫價格欄位。缺漏的欄位會在 DataFrame 中
        # 變成 NaN，由 save_data_to_json 既有的 pd.isna 過濾略過，
        # 絕不能填 0.0 —— 那會覆蓋掉檔案裡原本正確的價格。
        if quote:
            close_price = quote["收盤價"]
            record.update({
                "開盤價": quote["開盤價"],
                "最高價": quote["最高價"],
                "最低價": quote["最低價"],
                "收盤價": close_price,
                "成交股數(股)": quote["成交股數(股)"],
                "成交金額(元)": quote["成交金額(元)"],
                "成交筆數(筆)": quote["成交筆數(筆)"],
            })
            if total_lots is not None:
                record["估算買賣超金額(萬元)"] = round(total_lots * close_price / 10, 2)
        if stock_id in margin_by_stock:
            record.update(margin_by_stock[stock_id])
        records.append(record)
    return records


def _fetch_one_day(date_key: str, target_set: set, need_quote: bool, need_inst: bool,
                   today_date) -> dict:
    """單一交易日的全部抓取工作（在工作執行緒內執行，只做網路請求與解析，不碰共用狀態）。
    永遠回傳結果 dict、不拋例外：單日失敗只影響該日，由呼叫端記錄並繼續其他日期。"""
    result = {"date_key": date_key, "quotes": {}, "records": [], "no_trading": False, "error": None}
    try:
        if need_quote:
            result["quotes"], _ = fetch_mi_index_quotes(date_key, target_set)

        if need_inst:
            date_str = date_key.replace("-", "")
            margin_by_stock = _fetch_margin_by_stock(date_str, target_set)
            res_t86 = twse_get_json(
                f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALL&response=json"
            )
            stat = res_t86.get("stat", "")
            if stat == "OK":
                result["records"] = _build_institutional_records(
                    res_t86, date_key, target_set, result["quotes"], margin_by_stock
                )
            elif (
                datetime.strptime(date_key, "%Y-%m-%d").date() < today_date
                and _is_no_data_stat(stat)
                and not result["quotes"]  # 同日行情有資料就一定是交易日，不能因為法人端沒資料就記成休市
            ):
                result["no_trading"] = True
            elif _is_no_data_stat(stat):
                # 當天收盤後才會公布，或同日行情有資料——都不是休市，單純這次沒資料
                logger.info(f"[T86] {date_key} 尚無資料，本日略過")
            else:
                logger.warning(f"[T86] {date_key} 非預期回應 stat={stat!r}，本日略過")
    except Exception as e:
        result["error"] = str(e)
    return result


def fetch_market_data(target_stocks: list, days_by_stock: dict,
                      today: Optional[datetime] = None, max_workers: Optional[int] = None):
    """逐日抓取所有需要補的交易日（行情 + 融資券 + 三大法人），回傳
    (法人／融資券／行情合併後的 DataFrame, quote_lookup, 新確認的休市日集合)。

    日期是併發單位，每天內部的 3 個請求仍是序列。所有請求都經過 twse_client 的共用限流器，
    所以 max_workers 只影響「網路往返時間能疊多少」，不會把請求速率推過限流上限。
    某天所有目標股票都已有完整資料（非零收盤價／融資餘額）就直接略過，不重打。"""
    today = today or datetime.now()
    quote_lookup = {stock_id: {} for stock_id in target_stocks}
    max_days = max(days_by_stock.values()) if days_by_stock else 0
    if max_days <= 0 or not target_stocks:
        return pd.DataFrame(), quote_lookup, set()

    target_set = set(target_stocks)
    existing_data = {stock_id: load_stock_json(stock_id) for stock_id in target_stocks}
    no_trading_days = load_no_trading_days()

    def quote_complete(date_key: str) -> bool:
        return all(
            (record := existing_data[stock_id].get(date_key)) is not None and bool(_field(record, "close", 0))
            for stock_id in target_stocks
        )

    def institutional_complete(date_key: str) -> bool:
        # 注意：load_stock_json 會把 融資餘額(張) 正規化成 margin_balance，
        # 因此必須用 _field() 同時容忍兩種 key，否則永遠判定為不完整而重爬。
        # 價格是否為 0 不納入此判斷——缺價的日期只需補 MI_INDEX，不需要重打 T86/MI_MARGN。
        return all(
            (record := existing_data[stock_id].get(date_key)) is not None
            and _field(record, "margin_balance") is not None
            for stock_id in target_stocks
        )

    tasks = []
    skipped = 0
    for day in _valid_weekdays(max_days, today):
        date_key = day.strftime("%Y-%m-%d")
        if date_key in no_trading_days:
            skipped += 1
            continue
        need_quote = not quote_complete(date_key)
        need_inst = not institutional_complete(date_key)
        if not (need_quote or need_inst):
            skipped += 1
            continue
        tasks.append((date_key, need_quote, need_inst))

    workers = max_workers or get_twse_rate_settings()["max_workers"]
    total = len(tasks)
    fetch_status.update(
        5, 100,
        f"需抓取 {total} 個交易日（略過 {skipped} 個已完整／休市日），"
        f"併發 {workers}、目前限流間隔 {get_twse_limiter().interval:.2f}s"
    )

    results = {}
    if tasks:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_fetch_one_day, date_key, target_set, need_quote, need_inst, today.date())
                for date_key, need_quote, need_inst in tasks
            ]
            for done, future in enumerate(as_completed(futures), start=1):
                res = future.result()
                results[res["date_key"]] = res
                if res["error"]:
                    logger.warning(f"[TWSE] {res['date_key']} 抓取失敗，本日略過: {res['error']}")
                fetch_status.update(
                    5 + int(85 * done / total), 100,
                    f"逐日抓取 [{done}/{total}] {res['date_key']}"
                    + (f"（⚠️ 失敗: {res['error']}）" if res["error"] else "")
                )

    all_records = []
    newly_confirmed_no_trading = set()
    for date_key, _, _ in tasks:  # 依日期由新到舊的原順序彙整，與併發完成順序無關
        res = results[date_key]
        for stock_id, quote in res["quotes"].items():
            quote_lookup[stock_id][date_key] = quote
        all_records.extend(res["records"])
        if res["no_trading"]:
            newly_confirmed_no_trading.add(date_key)

    if newly_confirmed_no_trading:
        save_no_trading_days(no_trading_days | newly_confirmed_no_trading)
        dual_write_no_trading_days("tw", newly_confirmed_no_trading)

    return pd.DataFrame(all_records), quote_lookup, newly_confirmed_no_trading

def save_data_to_json(df: pd.DataFrame) -> list:
    os.makedirs(DATA_DIR, exist_ok=True)
    written_files = []
    margin_fields = set(_MI_MARGN_FIELD_MAP.keys())

    if df.empty:
        return written_files

    for stock_id, group in df.groupby("股票代號"):
        stock_id = str(stock_id)
        path = stock_json_path(stock_id)
        stock_data = load_stock_json(stock_id)

        touched_dates = []
        for record in group.to_dict(orient="records"):
            date_key = record["日期"]
            touched_dates.append(date_key)
            existing = stock_data.setdefault(date_key, {})
            detail = {}
            for k, v in record.items():
                if k in ("股票代號", "日期") or pd.isna(v):
                    continue
                # 最後一道防線：不讓 0 覆蓋既有的非零價格
                if k in _PRICE_FIELDS and not v and _field(existing, FIELD_MAP.get(k, k)):
                    continue
                detail[FIELD_MAP.get(k, k)] = int(v) if k in margin_fields else v
            existing.update(detail)

        normalized = {k: _normalize_keys(v) for k, v in stock_data.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)

        written_files.append(path)
        dual_write_daily_data(stock_id, "tw", {d: normalized[d] for d in touched_dates if d in normalized})

    return written_files

def run_fetch_process(target_stocks: Optional[list] = None, months: Optional[int] = None,
                      mode: str = "incremental", trigger_type: str = "manual"):
    stocks = target_stocks or get_target_stocks()
    started_at = datetime.now()
    try:
        m_range = months or get_months_range()

        mode_label = "重新抓取" if mode == "repair" else "增量更新"
        fetch_status.start(
            f"開始抓取 TWSE 資料 ({mode_label}) - 股票: {stocks}, 範圍: 近 {m_range} 個月"
        )

        global_days = m_range * 30
        days_by_stock = {}
        for stock_id in stocks:
            if mode == "repair":
                # 重抓模式一律使用完整視窗，才能補回中間缺漏的行情。
                # 這也讓行情窗與法人窗一致，避免兩者錯開造成的資料覆蓋。
                days_by_stock[stock_id] = global_days
                continue
            stock_data = load_stock_json(stock_id)
            existing_dates = sorted(stock_data.keys())
            if existing_dates:
                latest_date_str = existing_dates[-1]
                latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
                gap_days = (datetime.now() - latest_date).days + 1
                days_by_stock[stock_id] = min(gap_days, global_days)
            else:
                days_by_stock[stock_id] = global_days

        max_days = max(days_by_stock.values()) if days_by_stock else global_days

        fetch_status.update(2, 100, "同步證交所休市日曆...")
        sync_holiday_calendar(max_days)

        # 行情(MI_INDEX)、融資券(MI_MARGN)、三大法人(T86)合併成單一逐日迴圈，進度 5%~90%
        df, quote_lookup, _ = fetch_market_data(stocks, days_by_stock)

        if not df.empty:
            json_paths = save_data_to_json(df)
            fetch_status.update(92, 100, f"更新了 {len(json_paths)} 個股票資料庫檔案")

        patched = backfill_daily_quotes(stocks, quote_lookup)
        if patched:
            fetch_status.update(95, 100, f"修補了 {patched} 筆歷史行情數據")

        fetch_status.complete("全數資料更新完畢！")
        log_crawler_run("tw", trigger_type, started_at, "success", symbols_success=len(stocks))

    except Exception as e:
        fetch_status.fail(str(e))
        log_crawler_run("tw", trigger_type, started_at, "failed", symbols_failed=len(stocks), error_message=str(e))
