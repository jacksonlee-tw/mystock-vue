"""
services/macro_fetcher.py
FRED 總經指標與美元指數（DXY 代理）抓取（docs/16.AI技術分析/Phase4-輕量化新聞輿情與總經監控.md
§5.1，ADR-P4-05、ADR-P4-09）。

比照 services/news_fetcher.py 的兩段式落地（ADR-P4-04：新聞／PTT／總經資料皆採兩段式）：原始
回應先落地 JSON 快照（`data/_macro/raw/{indicator_code}/*.json`），再解析寫入 `macro_indicators`
（經 repositories/news_repository.py 的 run_async()／get_background_session() 橋接，同一套
「同步爬蟲→非同步 DB」既有慣例，不重新實作一份背景連線池）。

**ADR-P4-09**（新增，解決規格書 §15.4 原本標注「DXY 的具體資料來源未指定」的落差）：官方 ICE
DXY 期貨指數不是 FRED 的免費數列；改用 FRED 自家發布的 Nominal Broad U.S. Dollar Index
（series `DTWEXBGS`）作為免費替代——這是 FRED 官方文件明列的美元強弱免費替代指標，日頻更新，
2006 年後有完整資料。`indicator_code` 對外仍稱 `DXY`（比照 V23 migration 註解與前端顯示需求），
只是底層 FRED series_id 不同名。

Point-in-time 對齊（ADR-P4-05）：呼叫 FRED API 時指定 `output_type=4`（"Initial Release
Only"）——依 ALFRED 官方文件，這個輸出格式的 `realtime_start` 欄位就是「資料第一次對外公布的
日期」，直接拿來當 `release_date`，不需要另外呼叫 release-calendar 端點做比對配對，也不會因為
後續修訂版本（CPI／非農常見）而誤用修訂後的日期當作原始公布日。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from config import DATA_DIR, get_fred_api_key
from repositories.news_repository import NewsRepository, get_background_session, run_async
from services.fetcher import FetchStatusManager

logger = logging.getLogger("mystock-backend")

fetch_status = FetchStatusManager()

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
_MACRO_RAW_DIR = os.path.join(DATA_DIR, "_macro", "raw")

# indicator_code（本專案內部命名，見 V23__Create_news_and_macro_tables.sql 註解）
# -> FRED 官方 series_id 對照表。NFP／DXY 兩者官方 series_id 與我們的 indicator_code 不同名，
# 其餘三個（FEDFUNDS／CPI 用簡寫／US10Y 用自訂代號）刻意選了容易辨識的內部代號。
FRED_SERIES_MAP: Dict[str, str] = {
    "FEDFUNDS": "FEDFUNDS",   # Effective Federal Funds Rate（月頻）
    "NFP": "PAYEMS",          # All Employees, Total Nonfarm（美國非農就業人數，月頻）
    "CPI": "CPIAUCSL",        # CPI for All Urban Consumers: All Items（headline CPI，月頻）
    "US10Y": "DGS10",         # 10-Year Treasury Constant Maturity Rate（日頻）
    "DXY": "DTWEXBGS",        # Nominal Broad U.S. Dollar Index，ICE DXY 免費替代（ADR-P4-09，日頻）
}

LOOKBACK_DAYS = 400  # 略多於一年，確保月頻指標（CPI/NFP/FEDFUNDS）至少涵蓋最近一期


def _save_raw_snapshot(indicator_code: str, payload: Any) -> Optional[str]:
    """兩段式落地第一階段，比照 news_fetcher.py 的 `_save_raw_snapshot()`。"""
    try:
        day_dir = os.path.join(_MACRO_RAW_DIR, indicator_code)
        os.makedirs(day_dir, exist_ok=True)
        path = os.path.join(day_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        return path
    except Exception as e:
        logger.warning(f"[macro_fetcher] 原始快照落地失敗 ({indicator_code}): {e}")
        return None


def fetch_fred_series(indicator_code: str, fred_series_id: str, api_key: str) -> List[Dict[str, Any]]:
    """呼叫 FRED API 抓一個數列近 `LOOKBACK_DAYS` 天的「初次公布」觀測值。回傳
    `[{"indicator_date": date, "release_date": date, "value": float}, ...]`（由舊到新）。

    `value` 是 FRED 缺值標記（官方慣例用 `"."` 表示暫缺/未公布）或其他非數字字串時，
    該筆整筆跳過，不寫入假的 0（比照 fetcher.py 系列「缺值不可補 0」的既有教訓）。

    `realtime_start`／`realtime_end`：FRED 官方文件說這兩個參數「未指定時預設為今天」，
    但這個預設在搭配 `output_type=4` 時會把即時窗口收窄成「只限今天這一天發布的版本」，
    99% 情況下當天根本沒有任何數列首次公布，導致 API 直接回 400（`No vintage dates exist
    for the specified real-time period`）。實測踩過兩個坑，最終解法：
    - `realtime_start` 設成跟 `observation_start` 同一個日期（而非「開站至今」的 `1776-07-04`）
      ——後者對日頻數列（`DGS10`／`DXY`）會把即時窗口拉到近 5000+ 個 vintage 日，超過 FRED
      對 JSON 輸出格式的上限（2000 個），直接 400。
    - `realtime_end` 固定寫死 `"9999-12-31"`（FRED 文件明列的「即時期間最大值」哨兵值），
      不能填 `date.today()`——本機時區（UTC+8）比 FRED 伺服器所在時區早換日，午夜後、UTC
      尚未跨日的這段期間用本機今天的日期送出會被判定「晚於伺服器的今天」而 400。
    已對全部 5 個數列（月頻 3 個＋日頻 2 個）實測驗證可正常回傳資料。
    """
    observation_start = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    params = {
        "series_id": fred_series_id,
        "api_key": api_key,
        "file_type": "json",
        "output_type": 4,
        "observation_start": observation_start,
        "sort_order": "asc",
        "realtime_start": observation_start,
        "realtime_end": "9999-12-31",
    }
    resp = requests.get(FRED_BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    _save_raw_snapshot(indicator_code, payload)

    rows: List[Dict[str, Any]] = []
    for obs in payload.get("observations", []):
        try:
            value = float(obs.get("value"))
        except (TypeError, ValueError):
            continue
        try:
            indicator_dt = datetime.strptime(obs["date"], "%Y-%m-%d").date()
            release_dt = datetime.strptime(obs["realtime_start"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        rows.append({"indicator_date": indicator_dt, "release_date": release_dt, "value": value})
    return rows


async def _write_indicator_async(indicator_code: str, rows: List[Dict[str, Any]]) -> int:
    written = 0
    async with get_background_session() as session:
        repo = NewsRepository(session)
        for row in rows:
            await repo.upsert_macro_indicator(
                indicator_code=indicator_code, indicator_date=row["indicator_date"],
                release_date=row["release_date"], value=row["value"], source="FRED",
            )
            written += 1
        await session.commit()
    return written


def run_macro_fetch(trigger_type: str = "manual") -> Dict[str, Any]:
    """抓取全部總經指標（含 DXY 代理），逐一呼叫 FRED、寫入 `macro_indicators`。比照
    `news_fetcher.run_news_fetch()`：單一 `fetch_status` 單例保證同時只有一輪在跑；
    單一數列失敗不中止整輪（比照 P1 三來源互相獨立的精神），回傳每一項各自的成敗。"""
    fetch_status.start("開始抓取總經指標...")
    api_key = get_fred_api_key()
    if not api_key:
        fetch_status.fail("FRED_API_KEY 未設定")
        raise RuntimeError("FRED_API_KEY 未設定，無法抓取總經指標")

    results: Dict[str, Any] = {}
    total_written = 0
    try:
        codes = list(FRED_SERIES_MAP.items())
        for i, (indicator_code, fred_series_id) in enumerate(codes, start=1):
            fetch_status.update(i, len(codes), f"抓取 {indicator_code}（{fred_series_id}）...")
            try:
                rows = fetch_fred_series(indicator_code, fred_series_id, api_key)
                written = run_async(_write_indicator_async(indicator_code, rows)) if rows else 0
                results[indicator_code] = {"status": "ok", "fetched": len(rows), "written": written}
                total_written += written
            except Exception as e:
                logger.error(f"[macro_fetcher] {indicator_code} 抓取失敗: {e}")
                results[indicator_code] = {"status": "failed", "error": str(e)}

        fetch_status.complete(f"完成：共寫入 {total_written} 筆總經指標")
        return {"trigger_type": trigger_type, "total_written": total_written, "indicators": results}
    except Exception as e:
        logger.error(f"[macro_fetcher] 抓取失敗: {e}")
        fetch_status.fail(str(e))
        raise
