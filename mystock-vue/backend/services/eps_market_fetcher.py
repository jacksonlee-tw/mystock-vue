"""全市場季報 EPS 與損益摘要抓取（docs/16.AI技術分析/Phase2-籌碼面與基本面量化擴充.md §10.4 E-1）。

主要來源為 TWSE OpenAPI（免 key、無 WAF），比照 revenue_market_fetcher.py 的全市場一次抓取模式：

- `t187ap14_L`：上市公司各產業 EPS 統計資訊，一支請求即涵蓋全體上市公司，欄位最貼近需求
- `t187ap06_L_*`：各業別綜合損益表，補 t187ap14_L 未涵蓋到的公司（金控／保險／證券期貨等）

兩者皆為「最新一期季報快照」而非歷史全量，故落地策略是逐季累積（UPSERT），不做逐季回補。
歷史季別的逐檔補洞仍由 services/mops_eps_fetcher.py 負責（該端點受 WAF 限制，見其檔案註解）。

單位：EPS 為元；營收／營益／稅後淨利沿用來源原始單位（仟元），不在此換算，比照
revenue_market_fetcher.py 對 monthly_revenue.revenue 的處理。
"""
from datetime import date
import logging
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("mystock-backend")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_BASE_URL = "https://openapi.twse.com.tw/v1/opendata"

# 依序抓取並合併；先命中的資料集優先（同一 (symbol, year_quarter) 只有空欄位才由後者補上）。
_DATASETS = [
    "t187ap14_L",        # 各產業 EPS 統計資訊（涵蓋面最廣，欄位最精簡）
    "t187ap06_L_ci",     # 綜合損益表-一般業
    "t187ap06_L_fh",     # 綜合損益表-金控業
    "t187ap06_L_basi",   # 綜合損益表-金融業
    "t187ap06_L_ins",    # 綜合損益表-保險業
    "t187ap06_L_bd",     # 綜合損益表-證券期貨業
    "t187ap06_L_mim",    # 綜合損益表-異業
]

# 同一語意的欄位在不同資料集用了全形／半形括號與不同用詞，統一正規化後再比對。
_FIELD_ALIASES = {
    "symbol": ["公司代號"],
    "year": ["年度"],
    "season": ["季別"],
    "announced": ["出表日期"],
    "eps": ["基本每股盈餘(元)", "基本每股盈餘"],
    "revenue": ["營業收入", "收益", "收入", "淨收益"],
    "operating_income": ["營業利益", "營業利益(損失)", "營業利益(損失)淨額"],
    "net_income": ["稅後淨利", "本期淨利(淨損)", "本期稅後淨利(淨損)", "繼續營業單位本期淨利(淨損)"],
}


def _normalize_key(raw: Any) -> str:
    return (
        str(raw)
        .replace("（", "(")
        .replace("）", ")")
        .replace("　", "")
        .replace(" ", "")
        .strip()
    )


def _pick(normalized_item: Dict[str, Any], field: str) -> Any:
    for alias in _FIELD_ALIASES[field]:
        if alias in normalized_item:
            return normalized_item[alias]
    return None


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


def _to_ad_year(raw: Any) -> Optional[int]:
    year = _clean_int(raw)
    if year is None:
        return None
    # 財報資料集的「年度」為民國年（如 114）；少數情境已是西元年，兩者以 1911 為界區分。
    return year + 1911 if year < 1911 else year


def _normalize_year_quarter(raw_year: Any, raw_season: Any) -> Optional[str]:
    year = _to_ad_year(raw_year)
    season = _clean_int(raw_season)
    if year is None or season is None or not 1 <= season <= 4:
        return None
    return f"{year}-Q{season}"


def _normalize_announced_date(raw: Any) -> Optional[date]:
    """出表日期可能是民國 7 碼（1140815）或西元 8 碼（20260815）。"""
    s = str(raw or "").strip().replace("/", "").replace("-", "")
    if not re.fullmatch(r"\d{7,8}", s):
        return None
    try:
        if len(s) == 7:
            return date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


class EpsMarketFetcher:
    def _fetch_dataset(self, dataset: str) -> List[Dict[str, Any]]:
        url = f"{_BASE_URL}/{dataset}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            logger.warning(f"[EpsMarketFetcher] {dataset} 連線失敗: {e}")
            return []
        if r.status_code != 200:
            logger.warning(f"[EpsMarketFetcher] {dataset} HTTP {r.status_code}")
            return []
        try:
            data = r.json()
        except ValueError:
            logger.warning(f"[EpsMarketFetcher] {dataset} 回傳非 JSON")
            return []
        return data if isinstance(data, list) else []

    def fetch_twse_quarterly_eps(self) -> List[Dict[str, Any]]:
        """抓取 TWSE 最新一期全市場季報 EPS／損益摘要，回傳 quarterly_financials 的列格式。"""
        merged: Dict[tuple, Dict[str, Any]] = {}

        for dataset in _DATASETS:
            rows = self._fetch_dataset(dataset)
            if not rows:
                continue
            hit = 0
            for raw_item in rows:
                if not isinstance(raw_item, dict):
                    continue
                item = {_normalize_key(k): v for k, v in raw_item.items()}

                symbol = str(_pick(item, "symbol") or "").strip()
                year_quarter = _normalize_year_quarter(_pick(item, "year"), _pick(item, "season"))
                if not symbol or not year_quarter:
                    continue

                record = {
                    "symbol": symbol,
                    "year_quarter": year_quarter,
                    "market_type": "tw",
                    "eps": _clean_float(_pick(item, "eps")),
                    "revenue": _clean_int(_pick(item, "revenue")),
                    "operating_income": _clean_int(_pick(item, "operating_income")),
                    "net_income": _clean_int(_pick(item, "net_income")),
                    "announced_date": _normalize_announced_date(_pick(item, "announced")) or date.today(),
                    "source": "TWSE_OPENAPI",
                }

                existing = merged.get((symbol, year_quarter))
                if existing is None:
                    merged[(symbol, year_quarter)] = record
                    hit += 1
                else:
                    # 先命中的資料集優先，後者只補既有的空欄位（§3.7 不得把非空值覆寫為 NULL）
                    for field in ("eps", "revenue", "operating_income", "net_income"):
                        if existing.get(field) is None and record.get(field) is not None:
                            existing[field] = record[field]

            logger.info(f"[EpsMarketFetcher] {dataset} 取得 {len(rows)} 筆、新增 {hit} 檔")

        results = list(merged.values())
        logger.info(f"[EpsMarketFetcher] 全市場季報 EPS 合併後共 {len(results)} 筆")
        return results
