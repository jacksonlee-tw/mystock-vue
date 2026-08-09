import os
import json
import time
import calendar
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import threading

from config import DATA_DIR, BASE_DIR, get_target_stocks, get_months_range

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

# ── 輔助函式 ──────────────────────────────────────────────────

def stock_json_path(stock_id: str) -> str:
    return os.path.join(DATA_DIR, f"{stock_id}.json")

def load_stock_json(stock_id: str) -> dict:
    path = stock_json_path(stock_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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

def fetch_daily_quotes(target_stocks: list, days: int) -> dict:
    months = _months_in_range(days)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    quote_lookup = {stock_id: {} for stock_id in target_stocks}
    total = len(target_stocks) * len(months)
    n = 0

    for stock_id in target_stocks:
        for year, month in months:
            n += 1
            fetch_status.update(n, total * 2, f"行情抓取 [{n}/{total}]: {stock_id} {year}-{month:02d}")
            date_param = f"{year}{month:02d}01"
            url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date_param}&stockNo={stock_id}&response=json"
            try:
                res = requests.get(url, headers=headers, timeout=10).json()
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

            time.sleep(3)

    return quote_lookup

def backfill_daily_quotes(target_stocks: list, quote_lookup: dict) -> int:
    patched = 0
    for stock_id in target_stocks:
        stock_data = load_stock_json(stock_id)
        if not stock_data:
            continue

        changed = False
        for date_key, record in stock_data.items():
            if record.get("收盤價", 0) != 0 and "開盤價" in record:
                continue
            quote = quote_lookup.get(stock_id, {}).get(date_key)
            if not quote:
                continue
            record.update(quote)
            total_lots = record.get("合計買賣超(張)", 0)
            record["估算買賣超金額(萬元)"] = round(total_lots * quote["收盤價"] / 10, 2)
            changed = True
            patched += 1

        if changed:
            with open(stock_json_path(stock_id), "w", encoding="utf-8") as f:
                json.dump(stock_data, f, ensure_ascii=False, indent=2)

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

def fetch_stock_institutional_data(target_stocks: list, days: int, quote_lookup: dict):
    today = datetime.now()
    all_records = []
    existing_data = {stock_id: load_stock_json(stock_id) for stock_id in target_stocks}
    no_trading_days = load_no_trading_days()
    newly_confirmed_no_trading = set()

    def is_date_complete(stock_id: str, date_key: str) -> bool:
        record = existing_data[stock_id].get(date_key)
        return record is not None and "融資餘額(張)" in record

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
        fetch_status.update(current_step, total_steps, f"抓取三大法人及融資融券: {date_key}")

        margin_by_stock = {}
        margn_url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date_str}&selectType=ALL&response=json"
        try:
            res_margn = requests.get(margn_url, headers=headers, timeout=10).json()
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

        time.sleep(3)

        t86_url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALL&response=json"
        try:
            res_t86 = requests.get(t86_url, headers=headers, timeout=10).json()
            if res_t86.get("stat") == "OK":
                for row in res_t86.get("data", []):
                    stock_id = row[0].strip()
                    stock_name = row[1].strip()

                    if stock_id in target_stocks:
                        quote = quote_lookup.get(stock_id, {}).get(date_key, {})
                        close_price = quote.get("收盤價", 0.0)

                        foreign_lots = int(row[4].replace(",", "")) // 1000
                        trust_lots = int(row[7].replace(",", "")) // 1000
                        dealer_lots = int(row[10].replace(",", "")) // 1000
                        total_lots = int(row[11].replace(",", "")) // 1000
                        total_amount_wan = round(total_lots * close_price / 10, 2)

                        record = {
                            "日期": date_key,
                            "股票代號": stock_id,
                            "股票名稱": stock_name,
                            "開盤價": quote.get("開盤價", 0.0),
                            "最高價": quote.get("最高價", 0.0),
                            "最低價": quote.get("最低價", 0.0),
                            "收盤價": close_price,
                            "成交股數(股)": quote.get("成交股數(股)", 0),
                            "成交金額(元)": quote.get("成交金額(元)", 0),
                            "成交筆數(筆)": quote.get("成交筆數(筆)", 0),
                            "外資買賣超(張)": foreign_lots,
                            "投信買賣超(張)": trust_lots,
                            "自營商買賣超(張)": dealer_lots,
                            "合計買賣超(張)": total_lots,
                            "估算買賣超金額(萬元)": total_amount_wan,
                        }
                        if stock_id in margin_by_stock:
                            record.update(margin_by_stock[stock_id])

                        all_records.append(record)
            else:
                if target_date.date() < today.date():
                    newly_confirmed_no_trading.add(date_key)
        except Exception:
            pass

        time.sleep(3)

    if newly_confirmed_no_trading:
        save_no_trading_days(no_trading_days | newly_confirmed_no_trading)

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

        for record in group.to_dict(orient="records"):
            date_key = record["日期"]
            detail = {}
            for k, v in record.items():
                if k in ("股票代號", "日期") or pd.isna(v):
                    continue
                detail[k] = int(v) if k in margin_fields else v
            stock_data.setdefault(date_key, {}).update(detail)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(stock_data, f, ensure_ascii=False, indent=2)

        written_files.append(path)

    return written_files

def run_fetch_process(target_stocks: Optional[list] = None, months: Optional[int] = None):
    try:
        stocks = target_stocks or get_target_stocks()
        m_range = months or get_months_range()

        fetch_status.start(f"開始抓取 TWSE 資料 - 股票: {stocks}, 範圍: 近 {m_range} 個月")

        start_date = months_ago(m_range)
        days = (datetime.now() - start_date).days + 1

        fetch_status.update(1, 100, f"預先抓取每日行情 (STOCK_DAY)...")
        quote_lookup = fetch_daily_quotes(stocks, days)

        fetch_status.update(50, 100, f"抓取三大法人與融資融券 (T86 + MI_MARGN)...")
        df = fetch_stock_institutional_data(target_stocks=stocks, days=days, quote_lookup=quote_lookup)

        if not df.empty:
            json_paths = save_data_to_json(df)
            fetch_status.update(90, 100, f"更新了 {len(json_paths)} 個股票資料庫檔案")

        patched = backfill_daily_quotes(stocks, quote_lookup)
        if patched:
            fetch_status.update(95, 100, f"修補了 {patched} 筆歷史行情數據")

        fetch_status.complete("全數資料更新完畢！")

    except Exception as e:
        fetch_status.fail(str(e))
