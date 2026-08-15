"""個股產業標籤爬蟲（見 docs/10.加權指數/大盤指數功能規劃書.md §8.2）。

與「類股指數」（P5，見 services/index_fetcher.py 的 fetch_and_store_sector_snapshot()）是
兩個不同的概念：類股指數是每天變動的行情資料（走 ADR-I1「指數即標的」），產業標籤是相對
靜態的中繼資料（一檔股票屬於哪個產業，季度更新即可），因此獨立成自己的儲存與抓取邏輯，
不塞進 daily_stock_data。

台股：TWSE OpenAPI 上市公司基本資料（t187ap03_L）＋ TPEx 上櫃公司基本資料
（mopsfin_t187ap03_O），兩者皆為公開、不需金鑰的官方 API，直接提供「產業別」代碼，
對照 markets/tw_industries.py 的 TWSE_INDUSTRY_MAP 轉換成顯示名稱（同一份代碼表也被
P5 的類股指數快照使用，兩處資料自動對得起來，見規劃書 §8 的整合說明）。

美股：yfinance 沒有官方數字代碼，直接以 ticker.info 的 sector 英文字串當 industry_code。

儲存：JSON 模式落在 data/{market}/_meta/industries.json（{symbol: {industry_code,
industry_name}}），這是主要儲存（比照全站慣例：JSON 是原始且預設的來源，見 CLAUDE.md）；
Postgres 模式透過 db/dual_write.py 的 dual_write_symbol_industry() best-effort 雙寫，
失敗只記警告，不影響 JSON 落地。
"""
import json
import logging
import os
from typing import Dict, List, Optional

import requests
import yfinance as yf

from config import DATA_DIR
from db.dual_write import dual_write_symbol_industry
from markets.tw_industries import get_industry_name

logger = logging.getLogger("mystock-backend")

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
_TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
_REQUEST_TIMEOUT = 20

_META_DIR_NAME = "_meta"
_INDUSTRIES_FILE = "industries.json"

# yfinance sector 英文字串沒有官方中文名稱，維護一份簡單對照表；查不到的 sector
# 直接顯示原文，不阻斷流程（P-4「誠實標示資料缺口」的延伸：寧可顯示英文，也不要瞎猜）。
US_SECTOR_NAME_MAP = {
    "Technology": "科技",
    "Healthcare": "醫療保健",
    "Financial Services": "金融服務",
    "Consumer Cyclical": "非必需消費",
    "Consumer Defensive": "必需消費",
    "Industrials": "工業",
    "Energy": "能源",
    "Utilities": "公用事業",
    "Real Estate": "不動產",
    "Basic Materials": "原物料",
    "Communication Services": "通訊服務",
}

# industry_code 是穩定的短代碼（symbol_industry.industry_code 為 VARCHAR，需要一個不會
# 隨時間變動、長度可控的識別碼），不能直接拿 yfinance 原始 sector 字串當代碼——
# "Communication Services" 這類名稱曾經在實測中直接撐爆欄位寬度導致整批 upsert 失敗
# （多筆 VALUES 在同一個 INSERT 陳述式裡，一筆超長就會讓整批一起回滾）。
US_SECTOR_CODE_MAP = {
    "Technology": "tech",
    "Healthcare": "healthcare",
    "Financial Services": "financial",
    "Consumer Cyclical": "cons_cyclical",
    "Consumer Defensive": "cons_defensive",
    "Industrials": "industrials",
    "Energy": "energy",
    "Utilities": "utilities",
    "Real Estate": "real_estate",
    "Basic Materials": "materials",
    "Communication Services": "communication",
}


def _us_sector_code(sector: str) -> str:
    """未收錄在 US_SECTOR_CODE_MAP 的 sector（yfinance 未來可能新增分類）採防禦性處理：
    轉小寫、空白換底線、截斷在 20 字元內，確保不會再次撐爆資料庫欄位寬度。"""
    if sector in US_SECTOR_CODE_MAP:
        return US_SECTOR_CODE_MAP[sector]
    return sector.strip().lower().replace(" ", "_")[:20]


def industries_json_path(market: str) -> str:
    market_dir = os.path.join(DATA_DIR, market, _META_DIR_NAME)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, _INDUSTRIES_FILE)


def load_industries_json(market: str) -> Dict[str, dict]:
    path = industries_json_path(market)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_industries_json(market: str, data: Dict[str, dict]) -> None:
    path = industries_json_path(market)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)


def fetch_tw_industries() -> Dict[str, dict]:
    """一次抓全市場（上市＋上櫃）公司的產業別。回傳 {symbol: {industry_code, industry_name}}。"""
    result: Dict[str, dict] = {}

    sources = (
        (_TWSE_URL, "產業別", "公司代號", "TWSE 上市"),
        (_TPEX_URL, "SecuritiesIndustryCode", "SecuritiesCompanyCode", "TPEx 上櫃"),
    )
    for url, code_field, symbol_field, label in sources:
        try:
            rows = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT).json()
            count = 0
            for row in rows:
                symbol = str(row.get(symbol_field, "")).strip()
                code = str(row.get(code_field, "")).strip()
                if not symbol or not code:
                    continue
                result[symbol] = {"industry_code": code, "industry_name": get_industry_name(code)}
                count += 1
            logger.info(f"[產業] {label} 取得 {count} 檔產業別資料")
        except Exception as e:
            logger.warning(f"[產業] {label} 產業別抓取失敗: {e}")

    return result


def fetch_us_industries(symbols: List[str]) -> Dict[str, dict]:
    """逐檔查 yfinance sector。美股沒有官方數字代碼，直接用 sector 英文字串當 industry_code。"""
    result: Dict[str, dict] = {}
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).info
            sector = info.get("sector")
            if not sector:
                continue
            result[symbol] = {
                "industry_code": _us_sector_code(sector),
                "industry_name": US_SECTOR_NAME_MAP.get(sector, sector),
            }
        except Exception as e:
            logger.warning(f"[產業] {symbol} 產業別抓取失敗: {e}")
    return result


def sync_tw_industries() -> int:
    """更新台股全市場產業標籤（JSON 落地 + best-effort Postgres 雙寫）。回傳更新筆數。

    刻意抓「全市場」而非只抓目前追蹤清單：產業標籤資料量小（上市櫃合計約 2000 檔一次請求
    即可取得），先建好全市場對照表，未來新增追蹤股票時不需要再另外觸發一次產業抓取。
    """
    fetched = fetch_tw_industries()
    if not fetched:
        logger.warning("[產業] 台股產業別抓取結果為空，本次不更新")
        return 0

    existing = load_industries_json("tw")
    existing.update(fetched)
    save_industries_json("tw", existing)

    rows = [
        {"symbol": symbol, "market_type": "tw", "industry_code": v["industry_code"], "industry_name": v["industry_name"]}
        for symbol, v in fetched.items()
    ]
    dual_write_symbol_industry(rows)

    return len(fetched)


def sync_us_industries(symbols: List[str]) -> int:
    """更新指定美股清單的產業標籤。美股不像 TWSE 有全市場一次性 API，只能逐檔查 yfinance，
    因此只對目前追蹤清單（config.get_target_stocks(market='us')）抓取，而非全市場。"""
    fetched = fetch_us_industries(symbols)
    if not fetched:
        return 0

    existing = load_industries_json("us")
    existing.update(fetched)
    save_industries_json("us", existing)

    rows = [
        {"symbol": symbol, "market_type": "us", "industry_code": v["industry_code"], "industry_name": v["industry_name"]}
        for symbol, v in fetched.items()
    ]
    dual_write_symbol_industry(rows)

    return len(fetched)
