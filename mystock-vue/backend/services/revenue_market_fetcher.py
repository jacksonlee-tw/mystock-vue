"""全市場每月營業收入抓取與正規化（選股功能與爬蟲 規格書 §3.2 M/N、§3.4）。

支援 TWSE OpenAPI `t187ap05_L`，抓取全市場月營收、MoM、YoY 數據並落地至 `monthly_revenue` 表。
"""
from datetime import date, datetime
import logging
import re
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("mystock-backend")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _clean_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s in ("-", "--", "N/A", "null", "None"):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _clean_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s or s in ("-", "--", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _normalize_year_month(raw_ym: str) -> Optional[str]:
    """將民國年或西元年字串（如 '11506', '115/06', '2026-06', '202606'）標準化為 'YYYY-MM'。"""
    if not raw_ym:
        return None
    s = str(raw_ym).strip().replace("/", "-")
    # 符合 YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", s):
        return s
    # 符合 YYYYMM
    if re.match(r"^\d{6}$", s) and int(s[:4]) >= 1990:
        return f"{s[:4]}-{s[4:]}"
    # 符合 民國年 3碼 + 2碼月 (例: 11506)
    if re.match(r"^\d{5}$", s):
        roc_year = int(s[:3])
        month = s[3:]
        return f"{roc_year + 1911}-{month}"
    # 符合 民國年 3碼 + '-' + 2碼月 (例: 115-06)
    if re.match(r"^\d{3}-\d{2}$", s):
        roc_year, month = s.split("-")
        return f"{int(roc_year) + 1911}-{month}"
    return None


class RevenueMarketFetcher:
    def fetch_twse_monthly_revenue(self) -> List[Dict[str, Any]]:
        """抓取 TWSE 最新全市場月營收彙總 (t187ap05_L)。"""
        url = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                logger.warning(f"[RevenueMarketFetcher] TWSE t187ap05_L HTTP {r.status_code}")
                return []
            data = r.json()
            if not isinstance(data, list):
                return []

            results = []
            today = date.today()
            for item in data:
                symbol = str(item.get("公司代號") or item.get("出表代號") or "").strip()
                if not symbol:
                    continue

                raw_ym = item.get("資料年月") or item.get("資料月份") or ""
                ym = _normalize_year_month(raw_ym)
                if not ym:
                    # 若來源未提供年月，推導為上個月
                    first_of_this_month = today.replace(day=1)
                    last_month = (first_of_this_month - date.resolution).strftime("%Y-%m")
                    ym = last_month

                # 當月營收（元/千元，TWSE openapi 通常單位為元或千元，此處取原始整數）
                rev_val = _clean_int(item.get("營業收入-當月營收") or item.get("當月營收"))
                mom = _clean_float(item.get("營業收入-上月比較增減(%)") or item.get("上月比較增減(%)"))
                yoy = _clean_float(item.get("營業收入-去年同月增減(%)") or item.get("去年同月增減(%)"))

                results.append({
                    "symbol": symbol,
                    "year_month": ym,
                    "market_type": "tw",
                    "revenue": rev_val,
                    "mom_percent": mom,
                    "yoy_percent": yoy,
                    "announced_date": today,
                    "source": "TWSE_OPENAPI",
                })

            logger.info(f"[RevenueMarketFetcher] 成功抓取 TWSE 月營收共 {len(results)} 檔")
            return results
        except Exception as e:
            logger.error(f"[RevenueMarketFetcher] 抓取 TWSE 月營收失敗: {e}")
            return []
