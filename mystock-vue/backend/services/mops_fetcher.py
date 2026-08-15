"""MOPS（公開資訊觀測站）月營收爬蟲（爬蟲開發.md 第一、二、八節「月營收」）。

端點與參數格式已對照多個社群實作交叉驗證（POST ajax_t05st10_ifrs，
co_id + TYPEK(sii/otc/rotc) + year(民國年) + month）。注意：此端點對外部/雲端網段
IP 有嚴格 WAF（回傳「因為安全性考量」錯誤頁，非 JSON/表格），因此解析函式
一律容錯處理成「查無資料」，不可讓整個排程因單一請求被擋而中斷。
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta
from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from config import DATA_DIR, get_target_stocks, get_months_range
from services.fetcher import FetchStatusManager

logger = logging.getLogger("mystock-backend")

mops_fetch_status = FetchStatusManager()

_MOPS_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st10_ifrs"
_MOPS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mops.twse.com.tw/mops/web/t05st10_ifrs",
    "X-Requested-With": "XMLHttpRequest",
}
# 依序嘗試：上市、上櫃、興櫃，命中即停止（本專案未各別記錄個股的上市櫃別）。
_TYPEK_CANDIDATES = ["sii", "otc", "rotc"]

# 欄位定位規則：越精確（含「去年」）越要排在前面，避免被較寬鬆的規則搶先命中
# （例如「去年當月營收」若先比對「當月營收」會誤判成本月營收）。
_REVENUE_FIELD_RULES = [
    ("last_year_revenue", "去年", "當月營收"),
    ("cumulative_last_year_revenue", "去年", "累計營收"),
    ("cumulative_yoy_percent", None, "前期比較增減"),
    ("cumulative_yoy_percent", None, "累計增減"),
    ("yoy_percent", None, "去年同月增減"),
    ("yoy_percent", None, "去年當月增減"),
    ("mom_percent", None, "上月比較增減"),
    ("last_month_revenue", None, "上月營收"),
    ("cumulative_revenue", None, "累計營收"),
    ("revenue", None, "當月營收"),
]


def _match_revenue_field(column_text: str) -> Optional[str]:
    """依 _REVENUE_FIELD_RULES 由上而下比對，第一個符合的規則勝出。"""
    for field, must_contain, keyword in _REVENUE_FIELD_RULES:
        if must_contain is not None and must_contain not in column_text:
            continue
        if keyword in column_text:
            return field
    return None


def _flatten_columns(columns) -> List[str]:
    return [
        "".join(str(part) for part in col) if isinstance(col, tuple) else str(col)
        for col in columns
    ]


def _locate_revenue_columns(columns: List[str]) -> Optional[Dict[str, str]]:
    mapping: Dict[str, str] = {}
    for column_text, original in zip(_flatten_columns(columns), columns):
        field = _match_revenue_field(column_text)
        if field and field not in mapping:
            mapping[field] = original
    # 至少要能定位到「當月營收」才視為有效表格，其餘欄位缺漏則以 None 補齊。
    if "revenue" not in mapping:
        return None
    return mapping


def _to_number(raw: Any, as_float: bool) -> Optional[float]:
    text = str(raw).replace(",", "").replace("%", "").strip()
    if text in ("", "nan", "None", "-", "--"):
        return None
    try:
        return float(text) if as_float else int(float(text))
    except (ValueError, TypeError):
        return None


def _parse_monthly_revenue_html(html: str) -> Optional[dict]:
    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except ValueError:
        return None

    for df in tables:
        if df.shape[0] < 1:
            continue
        mapping = _locate_revenue_columns(list(df.columns))
        if mapping is None:
            continue
        row = df.iloc[0]
        result: Dict[str, Any] = {}
        for field, col in mapping.items():
            result[field] = _to_number(row[col], as_float="percent" in field)
        if result.get("revenue") is None:
            continue
        return result
    return None


def fetch_monthly_revenue_single(stock_id: str, year_ad: int, month: int) -> Optional[dict]:
    """抓取單一股票、單一月份的月營收；查無資料（含非個股、WAF 擋下）一律回傳 None。"""
    year_roc = year_ad - 1911
    for typek in _TYPEK_CANDIDATES:
        payload = {
            "encodeURIComponent": "1",
            "step": "1",
            "firstin": "1",
            "off": "1",
            "queryName": "co_id",
            "inpuType": "co_id",
            "TYPEK": typek,
            "co_id": stock_id,
            "year": str(year_roc),
            "month": f"{month:02d}",
        }
        try:
            resp = requests.post(_MOPS_URL, data=payload, headers=_MOPS_HEADERS, timeout=20)
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            logger.warning(f"[MOPS] {stock_id} {year_ad}-{month:02d} ({typek}) 連線失敗: {e}")
            continue

        if resp.status_code != 200:
            continue

        record = _parse_monthly_revenue_html(resp.text)
        if record:
            record["typek"] = typek
            return record
        time.sleep(1)
    return None


def _revenue_json_path(stock_id: str) -> str:
    market_dir = os.path.join(DATA_DIR, "tw")
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{stock_id}_revenue.json")


def load_stock_revenue(stock_id: str) -> dict:
    path = _revenue_json_path(stock_id)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_revenue_json(stock_id: str, data: dict) -> None:
    path = _revenue_json_path(stock_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)


def run_fetch_monthly_revenue(
    target_stocks: Optional[List[str]] = None,
    months: Optional[int] = None,
    force: bool = False,
    trigger_type: str = "manual",
) -> Dict[str, Any]:
    """抓取目標股票近 N 個月的月營收並落地成 JSON（data/tw/{stock_id}_revenue.json）。"""
    target_stocks = target_stocks or get_target_stocks(market="tw")
    months = months or get_months_range()

    mops_fetch_status.start(f"開始抓取月營收資料 - 股票: {target_stocks}")
    started_at = datetime.now()

    # 月營收約在次月 10 日前後才會公告完整，固定從「上個月」起回溯，避免每次都白跑當月查詢。
    cursor = datetime.now().replace(day=1) - timedelta(days=1)
    total_steps = max(1, len(target_stocks) * months)
    step = 0
    success_count = 0
    skipped_count = 0
    no_data_count = 0

    try:
        for stock_id in target_stocks:
            existing = load_stock_revenue(stock_id)
            month_cursor = cursor
            for _ in range(months):
                key = month_cursor.strftime("%Y-%m")
                step += 1

                if not force and key in existing:
                    mops_fetch_status.update(step, total_steps, f"[{stock_id}] {key} 已存在，跳過")
                    skipped_count += 1
                else:
                    mops_fetch_status.update(step, total_steps, f"[{stock_id}] 抓取月營收 {key}")
                    record = fetch_monthly_revenue_single(stock_id, month_cursor.year, month_cursor.month)
                    if record is None:
                        mops_fetch_status.update(
                            step, total_steps,
                            f"[{stock_id}] {key} 查無月營收資料（可能非個股或尚未公告），跳過"
                        )
                        no_data_count += 1
                    else:
                        record["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        existing[key] = record
                        success_count += 1
                    time.sleep(3)

                month_cursor = month_cursor.replace(day=1) - timedelta(days=1)

            _save_revenue_json(stock_id, existing)

        summary = {
            "success": success_count,
            "skipped": skipped_count,
            "no_data": no_data_count,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        mops_fetch_status.complete(f"月營收抓取完成：成功 {success_count}、跳過 {skipped_count}、無資料 {no_data_count}")
        logger.info(f"[MOPS] 月營收抓取完成 trigger={trigger_type} {summary}")
        return summary
    except Exception as e:
        mops_fetch_status.fail(str(e))
        logger.error(f"[MOPS] 月營收抓取失敗: {e}")
        raise
