"""大盤指數爬蟲（見 docs/10.加權指數/大盤指數功能規劃書.md ADR-I1/I3/I6、第三節）。

設計要點（對照規劃書）：
- **指數即標的（ADR-I1）**：指數資料落地格式與個股 JSON 完全同構
  （`{"YYYY-MM-DD": {"open":.., "high":.., "low":.., "close":.., "volume":.., "amount":.., "trades":..}}`），
  才能讓 `services/stock_service.py` 的 `aggregate_stock_data()` / `compute_ma_set()` 直接重用，
  不必為指數另寫一套聚合／均線邏輯。
- **指數不得混進個股清單（ADR-I3）**：JSON 落在 `data/{market}/_indices/{code}.json` 子目錄，
  `stock_service._list_stock_ids_json()` 只掃描 market 目錄下的 `.json` 檔（不遞迴進子目錄），
  天然排除指數，不需要額外的白名單/黑名單邏輯。
- **與個股爬蟲共用 fetch_status 單例（ADR-I3/I6）**：避免指數抓取與 STOCK_DAY/T86 等既有排程
  同時打 TWSE，互搶 rate limit；呼叫端（排程或 API）需自行以 `fetch_status.get_snapshot()["is_running"]`
  判斷是否忙碌中，本模組不重複做這層互斥判斷。
- **絕不寫 0（P-4 / CLAUDE.md 慣例）**：任何一步抓取失敗，該日期的欄位直接不落檔，不補 0.0，
  避免重蹈 `scripts/restore_price_from_legacy.py` 記錄的歷史問題。

已驗證的資料來源（2026-08-15 手動探測，詳見規劃書附錄 A）：
- 台股 OHLC：`rwd/zh/TAIEX/MI_5MINS_HIST?date=YYYYMM01&response=json`（月表，僅 TAIEX 本身提供，
  其他台股子指數如未含金融/電子、各類股，只有 `MI_INDEX` 當日快照，無月表可回補歷史 —— 見規劃書 R8）。
- 台股成交量值：`rwd/zh/afterTrading/FMTQIK?date=YYYYMM01&response=json`（月表，含成交股數/金額/筆數）。
- 美股：yfinance `Ticker(external_symbol).history()`，與 `services/us_fetcher.py` 相同做法。
  美股指數（尤其 ^DJI、^SOX）的 Volume 經常是 0，屬於資料來源本身限制（規劃書 R3），如實記錄不校正。
"""
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import Any, Dict, List, Optional

import pytz
import requests
import yaml
import yfinance as yf

from config import DATA_DIR, get_index_config_path, get_months_range
from db.dual_write import dual_write_daily_data, log_crawler_run
from markets.tw_industries import TWSE_INDUSTRY_MAP, sector_code
from services.fetcher import fetch_status, load_no_trading_days

logger = logging.getLogger("mystock-backend")

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_REQUEST_TIMEOUT = 10
_THROTTLE_SECONDS = 3  # 沿用 services/fetcher.py 對 TWSE 端點的既有節流間隔

INDEX_SUBDIR = "_indices"

_TW_TZ = pytz.timezone("Asia/Taipei")
# 與 services/scheduler.py 的台股排程時間一致：假設 TWSE 收盤後要到 14:30 資料才穩定可抓
_TW_DATA_READY_CUTOFF = dt_time(14, 30)


# ── 指數定義檔（比照 strategies/config_loader.py 的設計：每次呼叫重新解析，
#    檔案很小、改動頻率是「新增指數」等級，不需要快取，改 YAML 立即生效）──────────

@dataclass(frozen=True)
class IndexDefinition:
    code: str            # 系統代號，不含 '^'（規劃書 §1.2）
    market: str           # 'tw' | 'us'
    name: str
    short_name: str
    source: str            # 'twse' | 'yfinance'
    external_symbol: str  # 資料來源實際查詢用代號，例如 '^TWII'
    display_order: int = 0


def load_index_definitions(path: Optional[str] = None) -> List[IndexDefinition]:
    cfg_path = path or get_index_config_path()
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"[指數] 找不到指數定義檔 {cfg_path}，本次視為沒有任何指數")
        return []
    except yaml.YAMLError as e:
        logger.warning(f"[指數] 指數定義檔格式錯誤 {cfg_path}: {e}")
        return []

    definitions = []
    for item in raw.get("indices", []):
        try:
            definitions.append(IndexDefinition(
                code=item["code"],
                market=item["market"],
                name=item["name"],
                short_name=item.get("short_name", item["name"]),
                source=item["source"],
                external_symbol=item["external_symbol"],
                display_order=item.get("display_order", 0),
            ))
        except KeyError as e:
            logger.warning(f"[指數] 指數定義缺少必要欄位 {e}，已略過該筆: {item}")

    return sorted(definitions, key=lambda d: d.display_order)


def get_index_definitions(market: Optional[str] = None) -> List[IndexDefinition]:
    """回傳指數定義清單；指定 market 時只回傳該市場的指數。"""
    defs = load_index_definitions()
    if market:
        defs = [d for d in defs if d.market == market]
    return defs


def get_index_definition(code: str) -> Optional[IndexDefinition]:
    return next((d for d in load_index_definitions() if d.code == code), None)


# ── JSON 落地（data/{market}/_indices/{code}.json）─────────────────────────

def index_json_path(code: str, market: str) -> str:
    """指數 JSON 檔路徑。刻意放在 `_indices/` 子目錄而非與個股同層：
    `stock_service._list_stock_ids_json()` 用 `os.listdir()`（不遞迴）列出個股，
    子目錄天然被忽略，指數不會出現在個股清單／熱力圖／下拉選單中（ADR-I3）。"""
    market_dir = os.path.join(DATA_DIR, market, INDEX_SUBDIR)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{code}.json")


def load_index_json(code: str, market: str) -> dict:
    path = index_json_path(code, market)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_index_json(code: str, market: str, data: dict) -> None:
    path = index_json_path(code, market)
    sorted_data = dict(sorted(data.items()))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)


# ── 月份區間工具（與 services/fetcher.py 的 _months_in_range 邏輯相同，
#    獨立宣告一份避免跨模組 import 私有函式，見該檔案的既有慣例）────────────────

def _months_in_range(days: int) -> List[tuple]:
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


def _parse_number(raw: Any) -> Optional[float]:
    try:
        return float(str(raw).replace(",", ""))
    except (ValueError, TypeError):
        return None


# ── 台股：TWSE 擷取（目前僅支援 TAIEX/TWII，見模組頂部說明與規劃書 R8）───────────

def _fetch_twse_taiex_ohlc(months: List[tuple]) -> Dict[str, dict]:
    """加權指數歷史 OHLC（月表）。TWSE 目前只有這個端點提供指數層級的月表歷史，
    其餘台股子指數（未含金融/電子、各類股…）僅有 MI_INDEX 當日快照，無法比照回補。"""
    result: Dict[str, dict] = {}
    for year, month in months:
        date_param = f"{year}{month:02d}01"
        url = f"https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?date={date_param}&response=json"
        try:
            res = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT).json()
            if res.get("stat") == "OK":
                for row in res.get("data", []):
                    date_key = _roc_date_to_iso(row[0])
                    if date_key is None:
                        continue
                    o, h, l, c = (_parse_number(row[i]) for i in (1, 2, 3, 4))
                    if None in (o, h, l, c):
                        continue
                    result[date_key] = {"open": o, "high": h, "low": l, "close": c}
        except Exception as e:
            logger.warning(f"[指數] TAIEX OHLC 抓取失敗 ({year}-{month:02d}): {e}")
        time.sleep(_THROTTLE_SECONDS)
    return result


def _fetch_twse_fmtqik(months: List[tuple]) -> Dict[str, dict]:
    """大盤成交量值（月表，FMTQIK）：成交股數/金額/筆數，供成交量副圖使用（FR-IDX-04）。
    此端點回傳的是「全市場」成交統計，非 TAIEX 自身的量，語意上代表大盤當日量能。"""
    result: Dict[str, dict] = {}
    for year, month in months:
        date_param = f"{year}{month:02d}01"
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={date_param}&response=json"
        try:
            res = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT).json()
            if res.get("stat") == "OK":
                for row in res.get("data", []):
                    date_key = _roc_date_to_iso(row[0])
                    if date_key is None:
                        continue
                    volume, amount, trades = (_parse_number(row[i]) for i in (1, 2, 3))
                    entry = {}
                    if volume is not None:
                        entry["volume"] = int(volume)
                    if amount is not None:
                        entry["amount"] = int(amount)
                    if trades is not None:
                        entry["trades"] = int(trades)
                    if entry:
                        result[date_key] = entry
        except Exception as e:
            logger.warning(f"[指數] 大盤成交量值抓取失敗 ({year}-{month:02d}): {e}")
        time.sleep(_THROTTLE_SECONDS)
    return result


def fetch_tw_index_history(code: str, name: str, months: List[tuple]) -> Dict[str, dict]:
    """台股指數歷史資料（目前僅 TWII 有實作，見 `_fetch_twse_taiex_ohlc` 說明）。"""
    ohlc = _fetch_twse_taiex_ohlc(months)
    volumes = _fetch_twse_fmtqik(months)

    merged: Dict[str, dict] = {}
    for date_key, quote in ohlc.items():
        record = dict(quote)
        record.update(volumes.get(date_key, {}))
        record["date"] = date_key
        record["symbol"] = code
        record["name"] = name
        merged[date_key] = record
    return merged


# ── 美股：yfinance 擷取（與 services/us_fetcher.py 相同模式）───────────────────

def _fetch_yfinance_history(external_symbol: str, days: int = 365) -> Dict[str, dict]:
    ticker = yf.Ticker(external_symbol)
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    hist = ticker.history(start=start_date)
    result = {}
    if hist is None or hist.empty:
        return result
    for date_obj, row in hist.iterrows():
        date_key = date_obj.strftime("%Y-%m-%d")
        result[date_key] = {
            "open": float(row["Open"]), "high": float(row["High"]),
            "low": float(row["Low"]), "close": float(row["Close"]),
            "volume": int(row["Volume"]),
            "amount": int(row["Volume"] * row["Close"]),
        }
    return result


# ── 台股類股指數：MI_INDEX 當日快照（大盤指數功能規劃書 §8.1、R8）───────────────

def fetch_and_store_sector_snapshot(trade_date: Optional[str] = None) -> Dict[str, List[str]]:
    """類股指數當日快照。一次 MI_INDEX 請求取回全部 ~35 個類股指數，逐一比對名稱
    寫入各自的 JSON 檔（TWSE_INDUSTRY_MAP 是產業代碼 <-> 指數名稱的單一事實來源）。

    TWSE 這個端點提供收盤指數、漲跌點數、漲跌百分比，如實記錄收盤價、前日收盤與漲跌幅。
    trade_date 格式 YYYYMMDD（不含 '-'），預設今天。
    """
    date_param = trade_date or datetime.now().strftime("%Y%m%d")
    result: Dict[str, List[str]] = {"success": [], "failed": []}

    url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    try:
        res = requests.get(
            url,
            params={"date": date_param, "type": "IND", "response": "json"},
            headers=_HEADERS,
            timeout=_REQUEST_TIMEOUT,
        ).json()
    except Exception as e:
        logger.error(f"[指數] 類股指數快照抓取失敗 (date={date_param}): {e}")
        return result

    if res.get("stat") != "OK":
        logger.warning(f"[指數] 類股指數快照回應非 OK（date={date_param}）: {res.get('stat')}")
        return result

    tables = res.get("tables") or []
    rows = tables[0].get("data", []) if tables else []
    sector_data_by_name: Dict[str, dict] = {}
    for row in rows:
        if len(row) < 2:
            continue
        name = row[0].strip()
        close = _parse_number(row[1])
        if close is None:
            continue

        sign_str = row[2] if len(row) > 2 else ""
        diff = _parse_number(row[3]) if len(row) > 3 else None
        pct = _parse_number(row[4]) if len(row) > 4 else None

        is_down = ("-" in str(sign_str)) or (pct is not None and pct < 0) or (diff is not None and diff < 0)
        if diff is not None:
            diff = -abs(diff) if is_down else abs(diff)
        if pct is not None:
            pct = -abs(pct) if is_down else abs(pct)

        prev_close = round(close - (diff or 0), 2) if diff is not None else close

        sector_data_by_name[name] = {
            "close": close,
            "change": diff if diff is not None else 0.0,
            "change_percent": pct if pct is not None else 0.0,
            "prev_close": prev_close,
        }

    resp_date = res.get("date") or date_param
    date_key = f"{resp_date[:4]}-{resp_date[4:6]}-{resp_date[6:8]}"

    for industry_code, meta in TWSE_INDUSTRY_MAP.items():
        index_name = meta.get("index_name")
        code = sector_code(industry_code)
        if not index_name or index_name not in sector_data_by_name:
            result["failed"].append(code)
            continue

        sdata = sector_data_by_name[index_name]
        close = sdata["close"]
        prev_close = sdata["prev_close"]
        record = {
            "date": date_key,
            "symbol": code,
            "name": meta["name"],
            "open": prev_close if prev_close else close,
            "high": max(close, prev_close) if prev_close else close,
            "low": min(close, prev_close) if prev_close else close,
            "close": close,
            "change": sdata["change"],
            "change_percent": sdata["change_percent"],
            "prev_close": prev_close,
        }
        existing = load_index_json(code, "tw")
        existing[date_key] = record
        save_index_json(code, "tw", existing)
        dual_write_daily_data(code, "tw", {date_key: record})
        result["success"].append(code)

    return result


def backfill_sector_history(limit_days: int = 60) -> Dict[str, Any]:
    """類股歷史數據回補。依據台股大盤 (TWII) 已存在的交易日期列表，
    回補最近 limit_days 個交易日的 MI_INDEX 類股指數快照。"""
    twii_data = load_index_json("TWII", "tw")
    if not twii_data:
        today = datetime.now()
        dates_to_check = []
        for d in range(limit_days * 2):
            dt = today - timedelta(days=d)
            if dt.weekday() < 5:
                dates_to_check.append(dt.strftime("%Y%m%d"))
                if len(dates_to_check) >= limit_days:
                    break
        dates_to_check.reverse()
    else:
        all_twii_dates = sorted(twii_data.keys())
        target_dates = all_twii_dates[-limit_days:]
        dates_to_check = [d.replace("-", "") for d in target_dates]

    s01 = load_index_json(sector_code("01"), "tw")
    s01_dates = set(s01.keys())

    backfilled_dates = []
    for date_str in dates_to_check:
        iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        if iso_date not in s01_dates:
            res = fetch_and_store_sector_snapshot(date_str)
            if res["success"]:
                backfilled_dates.append(iso_date)
            time.sleep(0.3)

    return {"total_checked": len(dates_to_check), "backfilled_dates": backfilled_dates}


# ── 資料新鮮度判斷（供 /api/v1/indices/sync 在觸發抓取前先行判斷，見該端點註解）─────────

def get_latest_synced_tw_sector_date() -> Optional[str]:
    """目前已落地的台股類股指數最新日期，找不到資料回傳 None。
    以 01 塑膠工業類股為代表，與 backfill_sector_history() 判斷回補進度用的是同一份基準
    （該函式的 s01 變數），兩處保持一致。"""
    existing = load_index_json(sector_code("01"), "tw")
    return max(existing.keys()) if existing else None


def get_latest_expected_tw_trading_date(now: Optional[datetime] = None) -> str:
    """回傳台股「預期」應已有資料的最新交易日（YYYY-MM-DD，Asia/Taipei）。

    僅用週末 + 已知非交易日快取（services/fetcher.py 的 `_no_trading_days.json`，由歷史抓取
    邏輯逐步累積）做保守判斷，不是完整的證交所行事曆——尚未探測過的未來國定假日不會被排除。
    這對「同步按鈕先判斷資料是否已是最新」已經足夠：判斷錯誤的後果最多是多打一次 TWSE
    （仍會被 fetch_status 的互斥鎖與各爬蟲自身的增量比對保護），不會漏抓。"""
    current = now or datetime.now(_TW_TZ)
    if current.tzinfo is None:
        current = _TW_TZ.localize(current)

    candidate = current.date()
    if current.weekday() >= 5 or current.time() < _TW_DATA_READY_CUTOFF:
        candidate -= timedelta(days=1)

    no_trading_days = load_no_trading_days()
    while candidate.weekday() >= 5 or candidate.strftime("%Y-%m-%d") in no_trading_days:
        candidate -= timedelta(days=1)

    return candidate.strftime("%Y-%m-%d")


# ── 主流程 ───────────────────────────────────────────────────────────────

def run_index_fetch_process(
    market: Optional[str] = None,
    codes: Optional[List[str]] = None,
    months: Optional[int] = None,
    mode: str = "incremental",
    trigger_type: str = "manual",
) -> Dict[str, Any]:
    """指數抓取主流程（大盤指數功能規劃書 §3.3、ADR-I6）。

    與個股共用同一個 `fetch_status` 單例回報進度；呼叫端（排程 / API）須自行確認
    `fetch_status.get_snapshot()["is_running"]` 為 False 才呼叫本函式，本函式不做互斥判斷。

    mode='incremental'：只補「最後一筆資料之後」的缺口；mode='repair'：以完整區間重抓。
    """
    definitions = get_index_definitions(market)
    if codes:
        wanted = set(codes)
        definitions = [d for d in definitions if d.code in wanted]

    result: Dict[str, List[str]] = {"success": [], "failed": [], "skipped": []}
    total = len(definitions)
    if total == 0:
        logger.info(f"[指數] 沒有符合條件的指數定義 (market={market}, codes={codes})")
        return result

    started_at = datetime.now()
    m_range = months or get_months_range()
    fetch_status.start(f"開始抓取大盤指數資料（{mode}）- {[d.code for d in definitions]}")

    for i, definition in enumerate(definitions):
        fetch_status.update(i + 1, total, f"抓取指數 {definition.code}（{definition.name}）...")
        try:
            existing = load_index_json(definition.code, definition.market)
            existing_dates = sorted(existing.keys())
            need_full_range = mode == "repair" or not existing_dates

            if definition.source == "twse":
                if definition.code != "TWII":
                    logger.warning(
                        f"[指數] {definition.code} 標記為 twse 來源，但目前爬蟲僅實作 TAIEX(TWII) 的"
                        "月表歷史端點；其他台股子指數暫無法自動回補歷史（見規劃書附錄 A），本次略過"
                    )
                    result["skipped"].append(definition.code)
                    continue

                if need_full_range:
                    months_list = _months_in_range(days=m_range * 30)
                else:
                    last_dt = datetime.strptime(existing_dates[-1], "%Y-%m-%d")
                    days_needed = (datetime.now() - last_dt).days + 2
                    months_list = _months_in_range(days=days_needed)

                ohlc_dict = _fetch_twse_taiex_ohlc(months_list)
                fmtqik_dict = _fetch_twse_fmtqik(months_list)

                merged_dates = set(ohlc_dict.keys()) | set(fmtqik_dict.keys())
                for d in merged_dates:
                    ohlc = ohlc_dict.get(d, {})
                    vol = fmtqik_dict.get(d, {})
                    if d not in existing:
                        existing[d] = {
                            "date": d, "symbol": definition.code, "name": definition.name,
                            "open": 0, "high": 0, "low": 0, "close": 0,
                            "volume": 0, "amount": 0, "trades": 0,
                        }
                    existing[d].update(ohlc)
                    existing[d].update(vol)

                save_index_json(definition.code, definition.market, existing)
                dual_write_daily_data(definition.code, definition.market, existing)
                result["success"].append(definition.code)

            elif definition.source == "yfinance":
                if need_full_range:
                    days = m_range * 30
                    period = "3mo" if days <= 90 else "6mo" if days <= 180 else "1y" if days <= 365 else "5y"
                    fetched = fetch_us_index_history(definition.code, definition.external_symbol,
                                                      definition.name, period=period)
                else:
                    fetched = fetch_us_index_history(definition.code, definition.external_symbol,
                                                      definition.name, start_date=existing_dates[-1])
            else:
                logger.warning(f"[指數] 未知的資料來源 source={definition.source}（{definition.code}），略過")
                result["failed"].append(definition.code)
                continue

            if not fetched:
                result["skipped"].append(definition.code)
                continue

            existing.update(fetched)
            save_index_json(definition.code, definition.market, existing)
            dual_write_daily_data(definition.code, definition.market, fetched)
            result["success"].append(definition.code)

        except Exception as e:
            logger.error(f"[指數] {definition.code} 抓取失敗: {e}")
            result["failed"].append(definition.code)

    # 類股指數快照與上面「headline 指數」的迴圈是不同的抓取模式（單日快照 vs 月表歷史），
    # 但共用同一次呼叫入口，讓排程／腳本只需要呼叫一次 run_index_fetch_process() 就能同時
    # 涵蓋兩者：market 未指定或為 'tw'（類股是台股專屬概念），且沒有明確指定 codes
    # （指定 codes 代表呼叫端只想同步特定 headline 指數，不該連帶觸發額外的類股請求）。
    if codes is None and (market is None or market == "tw"):
        try:
            backfill_sector_history(limit_days=60)
            sector_result = fetch_and_store_sector_snapshot()
            result["success"].extend(sector_result["success"])
            result["failed"].extend(sector_result["failed"])
        except Exception as e:
            logger.error(f"[指數] 類股指數同步/回補失敗: {e}")

    fetch_status.complete(
        f"大盤指數資料更新完畢：成功 {len(result['success'])}，失敗 {len(result['failed'])}，略過 {len(result['skipped'])}"
    )
    status = "success" if not result["failed"] else ("partial_failure" if result["success"] else "failed")
    log_crawler_run("index", trigger_type, started_at, status,
                     symbols_success=len(result["success"]), symbols_failed=len(result["failed"]))
    return result
