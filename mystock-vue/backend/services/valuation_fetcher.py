"""全市場每日估值抓取與正規化（選股功能與爬蟲 規格書 §3.2、§3.4）。

支援 TWSE BWIBBU_d（歷史可指定日期）與 BWIBBU_ALL（當日快照），
將個股本益比 (PE)、股價淨值比 (PB)、殖利率 (Dividend Yield) 正規化後產出標準格式。
"""
from datetime import date, datetime
import logging
import re
from typing import Any, Dict, List, Optional
import requests

from config import get_market_fetch_throttle_seconds

logger = logging.getLogger("mystock-backend")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _clean_float(val: Any) -> Optional[float]:
    """清洗數值：過濾逗號、減號、空值、N/A，轉成 float；失敗回傳 None。"""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s in ("-", "--", "N/A", "null", "None"):
        return None
    try:
        f = float(s)
        # 虧損股或極端負值在 PE 視為 None
        return f
    except (ValueError, TypeError):
        return None


class ValuationFetcher:
    def __init__(self, throttle_seconds: Optional[int] = None):
        self.throttle_seconds = throttle_seconds if throttle_seconds is not None else get_market_fetch_throttle_seconds()

    def fetch_twse_valuation(self, trade_date: date) -> List[Dict[str, Any]]:
        """抓取 TWSE 指定日期的個股本益比、殖利率及淨值比。"""
        date_str = trade_date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={date_str}&selectType=ALL&response=json"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[ValuationFetcher] TWSE BWIBBU_d HTTP {r.status_code} ({date_str})")
                return []
            data = r.json()
            if data.get("stat") != "OK":
                # 非交易日或無資料
                return []

            fields = data.get("fields", [])
            raw_data = data.get("data", [])
            if not raw_data:
                return []

            # 動態定位欄位索引
            sym_idx, name_idx, pe_idx, yield_idx, pb_idx = 0, 1, 2, 3, 4
            for i, f in enumerate(fields):
                if "證券代號" in f or "代號" in f:
                    sym_idx = i
                elif "證券名稱" in f or "名稱" in f:
                    name_idx = i
                elif "本益比" in f:
                    pe_idx = i
                elif "殖利率" in f:
                    yield_idx = i
                elif "淨值比" in f:
                    pb_idx = i

            results = []
            for row in raw_data:
                if len(row) <= max(sym_idx, pe_idx, yield_idx, pb_idx):
                    continue
                symbol = str(row[sym_idx]).strip()
                # 排除非股票/ETF 的特殊代號若有需要
                if not symbol:
                    continue

                pe = _clean_float(row[pe_idx])
                div_yield = _clean_float(row[yield_idx])
                pb = _clean_float(row[pb_idx])

                results.append({
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "market_type": "tw",
                    "exchange": "TWSE",
                    "pe_ratio": pe,
                    "pb_ratio": pb,
                    "dividend_yield": div_yield,
                    "market_cap": None,   # 市值後續可由行情價格 × 股本計算或來源補充
                    "mcap_rank": None,
                    "source": "BWIBBU_d",
                })

            return results
        except Exception as e:
            logger.error(f"[ValuationFetcher] 抓取 TWSE 估值失敗 ({date_str}): {e}")
            return []

    def fetch_twse_valuation_snapshot(self) -> List[Dict[str, Any]]:
        """當日快照備援（BWIBBU_ALL OpenAPI）。"""
        url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        today = date.today()
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                return []
            arr = r.json()
            results = []
            for item in arr:
                symbol = str(item.get("Code", "")).strip()
                if not symbol:
                    continue
                results.append({
                    "symbol": symbol,
                    "trade_date": today,
                    "market_type": "tw",
                    "exchange": "TWSE",
                    "pe_ratio": _clean_float(item.get("PEratio")),
                    "pb_ratio": _clean_float(item.get("PBratio")),
                    "dividend_yield": _clean_float(item.get("DividendYield")),
                    "market_cap": None,
                    "mcap_rank": None,
                    "source": "BWIBBU_ALL",
                })
            return results
        except Exception as e:
            logger.error(f"[ValuationFetcher] 抓取 TWSE 估值快照失敗: {e}")
            return []
