import os
import json
import time
import random
import calendar
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import threading

from config import DATA_DIR, BASE_DIR, get_target_stocks, get_months_range
from db.dual_write import dual_write_daily_data, dual_write_no_trading_days, log_crawler_run

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

# ── TWSE 請求（含重試）──────────────────────────────────────────
# 證交所對高頻爬蟲會直接 drop 連線或延遲回應，單純拉長 timeout 不夠，
# 需搭配 Session（重用連線 + 固定 Referer）與指數退避重試。

_TWSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
}
_TWSE_TIMEOUT = (5, 20)  # (連線 timeout, 讀取 timeout)

_twse_session = requests.Session()
_twse_session.headers.update(_TWSE_HEADERS)


def _twse_get_json(url: str, max_retries: int = 3) -> dict:
    """對 TWSE API 發送請求，遇到逾時/連線錯誤時以指數退避 + jitter 重試。
    重試耗盡後拋出例外，由呼叫端既有的 try/except 決定該筆資料視為抓取失敗。"""
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = _twse_session.get(url, timeout=_TWSE_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            last_exc = e
            if attempt == max_retries - 1:
                break
            backoff = (2 ** attempt) * 5 + random.uniform(1, 3)
            logger.warning(
                f"[TWSE] 請求逾時/失敗（第 {attempt + 1}/{max_retries} 次），"
                f"{backoff:.1f}s 後重試: {url} ({e})"
            )
            time.sleep(backoff)
    raise last_exc

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

def _roc_date_to_iso(roc_date: str) -> Optional[str]:
    try:
        roc_year, month, day = roc_date.split("/")
        return f"{int(roc_year) + 1911}-{int(month):02d}-{int(day):02d}"
    except (ValueError, AttributeError):
        return None

_STOCK_DAY_FIELD_MAP = {
    "開盤價": (3, float),
    "最高價": (4, float),
    "最低價": (5, float),
    "收盤價": (6, float),
    "成交股數(股)": (1, int),
    "成交金額(元)": (2, int),
    "成交筆數(筆)": (8, int),
}

def _parse_quote_field(row: list, index: int, cast):
    try:
        return cast(str(row[index]).replace(",", ""))
    except (ValueError, IndexError, TypeError):
        return None

def fetch_daily_quotes(target_stocks: list, days_by_stock: dict) -> dict:
    quote_lookup = {stock_id: {} for stock_id in target_stocks}
    
    months_by_stock = {}
    total = 0
    for stock_id in target_stocks:
        stock_days = days_by_stock.get(stock_id, 90)
        m = _months_in_range(stock_days)
        months_by_stock[stock_id] = m
        total += len(m)
        
    n = 0

    for stock_id in target_stocks:
        for year, month in months_by_stock[stock_id]:
            n += 1
            date_param = f"{year}{month:02d}01"
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date_param}&stockNo={stock_id}&response=json"
            fetch_status.update(n, total * 2, f"行情抓取 [{n}/{total}]: {stock_id} {year}-{month:02d} | URL: {url}")
            try:
                res = _twse_get_json(url)
                if res.get("stat") == "OK":
                    rows = res.get("data", [])
                    for row in rows:
                        date_key = _roc_date_to_iso(row[0])
                        if date_key is None:
                            continue
                        close = _parse_quote_field(row, 6, float)
                        if close is None:
                            continue
                        quote = {"收盤價": close}
                        for field, (index, cast) in _STOCK_DAY_FIELD_MAP.items():
                            if field == "收盤價":
                                continue
                            value = _parse_quote_field(row, index, cast)
                            quote[field] = value if value is not None else cast(0)
                        quote_lookup[stock_id][date_key] = quote
            except Exception as e:
                fetch_status.update(n, total * 2, f"⚠️ 行情抓取失敗 ({stock_id} {year}-{month:02d}): {e}")

            time.sleep(random.uniform(3.5, 5.5))

    return quote_lookup

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

def fetch_stock_institutional_data(target_stocks: list, days: int, quote_lookup: dict):
    today = datetime.now()
    all_records = []
    existing_data = {stock_id: load_stock_json(stock_id) for stock_id in target_stocks}
    no_trading_days = load_no_trading_days()
    newly_confirmed_no_trading = set()

    def is_date_complete(stock_id: str, date_key: str) -> bool:
        # 注意：load_stock_json 會把 融資餘額(張) 正規化成 margin_balance，
        # 因此這裡必須用 _field() 同時容忍兩種 key，否則永遠判定為不完整而重爬。
        # 價格是否為 0 不納入判斷 —— 缺價的日期交由 backfill_daily_quotes 以
        # STOCK_DAY 修補，不需要重打 T86/MI_MARGN。
        record = existing_data[stock_id].get(date_key)
        return record is not None and _field(record, "margin_balance") is not None

    skipped_count = 0

    valid_days = [today - timedelta(days=i) for i in range(days) if (today - timedelta(days=i)).weekday() < 5]
    total_valid = len(valid_days)

    months_count = len(_months_in_range(days))
    base_step = len(target_stocks) * months_count

    for idx, target_date in enumerate(valid_days):
        current_step = base_step + idx + 1
        total_steps = base_step + total_valid

        date_key = target_date.strftime("%Y-%m-%d")
        if date_key in no_trading_days or all(is_date_complete(stock_id, date_key) for stock_id in target_stocks):
            skipped_count += 1
            fetch_status.update(current_step, total_steps, f"跳過已知日期 {date_key}")
            continue

        date_str = target_date.strftime("%Y%m%d")
        margn_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
        t86_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALL&response=json"
        fetch_status.update(current_step, total_steps, f"抓取三大法人及融資融券 [{date_key}] | URL: {t86_url}")

        margin_by_stock = {}
        try:
            res_margn = _twse_get_json(margn_url)
            if res_margn.get("stat") == "OK":
                tables = res_margn.get("tables", [])
                stock_rows = tables[1].get("data", []) if len(tables) > 1 else []
                for row in stock_rows:
                    row_stock_id = row[0].strip()
                    if row_stock_id in target_stocks:
                        parsed = _parse_margin_row(row)
                        if parsed is not None:
                            margin_by_stock[row_stock_id] = parsed
        except Exception as e:
            pass

        time.sleep(random.uniform(3.5, 5.5))

        try:
            res_t86 = _twse_get_json(t86_url)
            if res_t86.get("stat") == "OK":
                columns = _locate_t86_columns(res_t86.get("fields", []))
                if columns is None:
                    logger.error(
                        f"[T86] {date_key} 欄位定位失敗，本日不落檔法人數字（欄位: {res_t86.get('fields')}）"
                    )

                for row in res_t86.get("data", []):
                    stock_id = row[0].strip()
                    stock_name = row[1].strip()

                    if stock_id in target_stocks:
                        quote = quote_lookup.get(stock_id, {}).get(date_key, {})

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

                        all_records.append(record)
            else:
                if target_date.date() < today.date():
                    newly_confirmed_no_trading.add(date_key)
        except Exception:
            pass

        time.sleep(random.uniform(3.5, 5.5))

    if newly_confirmed_no_trading:
        save_no_trading_days(no_trading_days | newly_confirmed_no_trading)
        dual_write_no_trading_days("tw", newly_confirmed_no_trading)

    return pd.DataFrame(all_records)

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

        fetch_status.update(1, 100, f"預先抓取每日行情 (STOCK_DAY)...")
        quote_lookup = fetch_daily_quotes(stocks, days_by_stock)

        fetch_status.update(50, 100, f"抓取三大法人與融資融券 (T86 + MI_MARGN)...")
        df = fetch_stock_institutional_data(target_stocks=stocks, days=max_days, quote_lookup=quote_lookup)

        if not df.empty:
            json_paths = save_data_to_json(df)
            fetch_status.update(90, 100, f"更新了 {len(json_paths)} 個股票資料庫檔案")

        patched = backfill_daily_quotes(stocks, quote_lookup)
        if patched:
            fetch_status.update(95, 100, f"修補了 {patched} 筆歷史行情數據")

        fetch_status.complete("全數資料更新完畢！")
        log_crawler_run("tw", trigger_type, started_at, "success", symbols_success=len(stocks))

    except Exception as e:
        fetch_status.fail(str(e))
        log_crawler_run("tw", trigger_type, started_at, "failed", symbols_failed=len(stocks), error_message=str(e))
