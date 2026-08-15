"""MOPS（公開資訊觀測站）季報 EPS 爬蟲（爬蟲開發.md 第一、二、八節「季財報 / EPS」）。

端點為 POST ajax_t163sb04（綜合損益表），payload 型式比照 services/mops_fetcher.py 的
月營收端點（ajax_t05st10_ifrs）：都是 co_id + TYPEK(sii/otc/rotc) + year(民國年)，差異只在
用 season(01~04) 取代 month。

**已知限制**：此端點與月營收同樣掛在 mops.twse.com.tw，對外部/雲端網段 IP 有嚴格 WAF，
開發環境無法直接發出真實請求驗證回傳表格的實際欄位順序。以下的列標籤比對規則
（_EPS_ROW_RULES）與金額欄位定位（_first_amount_value）是依 MOPS 綜合損益表慣用格式
（會計項目 + 本期金額 + 本期% + 去年同期金額 + 去年同期%）推導，正式環境上線前務必先在
台灣網段跑一次 fetch_quarterly_eps_single() 驗證，若欄位對不上只需要調整這兩個函式，
不影響其餘的抓取／落地／API 流程（詳見 docs/3.爬蟲開發/待辦清單.md 第 2 項）。
"""
import json
import logging
import os
import time
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from config import DATA_DIR, get_quarters_range, get_target_stocks
from services.fetcher import FetchStatusManager

logger = logging.getLogger("mystock-backend")

eps_fetch_status = FetchStatusManager()

_EPS_URL = "https://mops.twse.com.tw/mops/web/ajax_t163sb04"
_EPS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mops.twse.com.tw/mops/web/t163sb04",
    "X-Requested-With": "XMLHttpRequest",
}
# 依序嘗試：上市、上櫃、興櫃，命中即停止（本專案未各別記錄個股的上市櫃別，比照月營收爬蟲）。
_TYPEK_CANDIDATES = ["sii", "otc", "rotc"]

# 依標籤字串比對綜合損益表逐列項目；越精確的規則要排在前面，避免被較寬鬆的規則搶先命中。
_EPS_ROW_RULES: List[Tuple[str, str]] = [
    ("eps", "基本每股盈餘"),
    ("net_income", "本期淨利"),
    ("net_income", "淨利（淨損）"),
    ("revenue", "營業收入合計"),
    ("revenue", "營業收入"),
]


def _match_eps_row(label_text: str) -> Optional[str]:
    """依 _EPS_ROW_RULES 由上而下比對，第一個符合的規則勝出。"""
    for field, keyword in _EPS_ROW_RULES:
        if keyword in label_text:
            return field
    return None


def _to_number(raw: Any, as_float: bool) -> Optional[float]:
    text = str(raw).replace(",", "").replace("%", "").strip()
    if text in ("", "nan", "None", "-", "--"):
        return None
    try:
        return float(text) if as_float else int(float(text))
    except (ValueError, TypeError):
        return None


def _flatten_columns(columns) -> List[str]:
    return [
        "".join(str(part) for part in col) if isinstance(col, tuple) else str(col)
        for col in columns
    ]


def _first_amount_value(row: "pd.Series", columns: List[str]) -> Optional[float]:
    """取列中第一個「非百分比」的金額欄位。MOPS 綜合損益表慣例上，項目名稱後緊接的
    就是本期金額欄，其後才是本期%／去年同期金額／去年同期%，故只需跳過含 % 的欄位。"""
    for col_text, col in zip(columns[1:], row.index[1:]):
        if "%" in col_text:
            continue
        value = _to_number(row[col], as_float=False)
        if value is not None:
            return value
    return None


def _parse_quarterly_eps_html(html: str) -> Optional[dict]:
    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except ValueError:
        return None

    result: Dict[str, Any] = {}
    for df in tables:
        if df.shape[0] < 1 or df.shape[1] < 2:
            continue
        columns = _flatten_columns(df.columns)
        for _, row in df.iterrows():
            label = str(row.iloc[0])
            field = _match_eps_row(label)
            if field is None or field in result:
                continue
            if field == "eps":
                value = _to_number(row.iloc[1], as_float=True)
            else:
                value = _first_amount_value(row, columns)
            if value is not None:
                result[field] = value

    # 至少要能定位到「基本每股盈餘」才視為有效表格，其餘欄位缺漏則略過。
    if "eps" not in result:
        return None
    return result


def fetch_quarterly_eps_single(stock_id: str, year_ad: int, season: int) -> Optional[dict]:
    """抓取單一股票、單一季別的 EPS；查無資料（含非個股、尚未公告、WAF 擋下）一律回傳 None。"""
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
            "season": f"{season:02d}",
        }
        try:
            resp = requests.post(_EPS_URL, data=payload, headers=_EPS_HEADERS, timeout=20)
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            logger.warning(f"[MOPS-EPS] {stock_id} {year_ad}Q{season} ({typek}) 連線失敗: {e}")
            continue

        if resp.status_code != 200:
            continue

        record = _parse_quarterly_eps_html(resp.text)
        if record:
            record["typek"] = typek
            return record
        time.sleep(1)
    return None


def _eps_json_path(stock_id: str) -> str:
    market_dir = os.path.join(DATA_DIR, "tw")
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{stock_id}_eps.json")


def load_stock_eps(stock_id: str) -> dict:
    path = _eps_json_path(stock_id)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_eps_json(stock_id: str, data: dict) -> None:
    path = _eps_json_path(stock_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)


def _current_quarter(dt: datetime) -> Tuple[int, int]:
    return dt.year, (dt.month - 1) // 3 + 1


def _prev_quarter(year: int, season: int) -> Tuple[int, int]:
    if season == 1:
        return year - 1, 4
    return year, season - 1


def run_fetch_quarterly_eps(
    target_stocks: Optional[List[str]] = None,
    quarters: Optional[int] = None,
    force: bool = False,
    trigger_type: str = "manual",
) -> Dict[str, Any]:
    """抓取目標股票近 N 季的 EPS 並落地成 JSON（data/tw/{stock_id}_eps.json）。"""
    target_stocks = target_stocks or get_target_stocks(market="tw")
    quarters = quarters or get_quarters_range()

    eps_fetch_status.start(f"開始抓取季報 EPS 資料 - 股票: {target_stocks}")
    started_at = datetime.now()

    # 季報有法定公告期限（Q1~Q3 約季底後 45 天，Q4/年報約隔年 3/31），當季資料在期限前
    # 必然抓不到，固定從「上一季」起回溯，避免每次都白跑當季查詢（比照月營收爬蟲的做法）。
    year, season = _prev_quarter(*_current_quarter(datetime.now()))
    total_steps = max(1, len(target_stocks) * quarters)
    step = 0
    success_count = 0
    skipped_count = 0
    no_data_count = 0

    try:
        for stock_id in target_stocks:
            existing = load_stock_eps(stock_id)
            q_year, q_season = year, season
            for _ in range(quarters):
                key = f"{q_year}-Q{q_season}"
                step += 1

                if not force and key in existing:
                    eps_fetch_status.update(step, total_steps, f"[{stock_id}] {key} 已存在，跳過")
                    skipped_count += 1
                else:
                    eps_fetch_status.update(step, total_steps, f"[{stock_id}] 抓取季報 EPS {key}")
                    record = fetch_quarterly_eps_single(stock_id, q_year, q_season)
                    if record is None:
                        eps_fetch_status.update(
                            step, total_steps,
                            f"[{stock_id}] {key} 查無 EPS 資料（可能非個股或尚未公告），跳過"
                        )
                        no_data_count += 1
                    else:
                        record["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        existing[key] = record
                        success_count += 1
                    time.sleep(3)

                q_year, q_season = _prev_quarter(q_year, q_season)

            _save_eps_json(stock_id, existing)

        summary = {
            "success": success_count,
            "skipped": skipped_count,
            "no_data": no_data_count,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        eps_fetch_status.complete(f"季報 EPS 抓取完成：成功 {success_count}、跳過 {skipped_count}、無資料 {no_data_count}")
        logger.info(f"[MOPS-EPS] 季報 EPS 抓取完成 trigger={trigger_type} {summary}")
        return summary
    except Exception as e:
        eps_fetch_status.fail(str(e))
        logger.error(f"[MOPS-EPS] 季報 EPS 抓取失敗: {e}")
        raise
