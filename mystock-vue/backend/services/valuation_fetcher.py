"""全市場每日估值抓取與正規化（選股功能與爬蟲 規格書 §3.2、§3.4）。

支援 TWSE BWIBBU_d（歷史可指定日期）與 BWIBBU_ALL（當日快照），
將個股本益比 (PE)、股價淨值比 (PB)、殖利率 (Dividend Yield) 正規化後產出標準格式。

市值 (market_cap) 與市值排名 (mcap_rank，僅 fetch_twse_valuation() 主來源提供，見該函式
docstring）：市值 = BWIBBU_d 當日收盤價 × t187ap03_L 已發行股數，修復
docs/16.AI技術分析/Phase2-籌碼面與基本面量化擴充.md 記錄的「市值 0% 覆蓋率」已知缺口。
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


def _assign_mcap_rank(records: List[Dict[str, Any]]) -> None:
    """依 market_cap 由大到小原地回填 mcap_rank（1 起算）；market_cap 為 None 的列
    不參與排名、mcap_rank 維持 None（缺席即缺席，不得排在最後幾名頂替）。"""
    ranked = sorted((r for r in records if r["market_cap"] is not None), key=lambda r: r["market_cap"], reverse=True)
    for i, r in enumerate(ranked, start=1):
        r["mcap_rank"] = i


SHARES_OUTSTANDING_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"


def _clean_shares(val: Any) -> Optional[int]:
    """清洗已發行股數：純數字字串轉 int，失敗或非正值一律回傳 None（缺席即缺席，
    不得以 0 頂替——0 股會讓市值算成 0，跟「這檔沒有市值」是完全不同的語意）。"""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if not s:
        return None
    try:
        n = int(s)
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None


class ValuationFetcher:
    def __init__(self, throttle_seconds: Optional[int] = None):
        self.throttle_seconds = throttle_seconds if throttle_seconds is not None else get_market_fetch_throttle_seconds()
        # 已發行股數變動極少（僅隨增減資等資本事件變動，不像 PE/PB 天天變），一次抓全市場後
        # 快取在實例上，同一次爬蟲執行（可能對多個 trade_date 呼叫 fetch_twse_valuation()）
        # 不重複打這支 API；下次建立新的 ValuationFetcher（例如隔天排程重新執行）才會重抓，
        # 天然對齊「每天重算一次」的頻率，不需要另外設計過期判斷。
        self._shares_outstanding_cache: Optional[Dict[str, int]] = None

    def fetch_tw_shares_outstanding(self) -> Dict[str, int]:
        """抓取上市公司目前已發行普通股數，供市值計算（市值 = 收盤價 × 已發行股數）使用。

        來源：TWSE OpenAPI 上市公司基本資料（t187ap03_L）——與 services/industry_fetcher.py
        抓「產業別」欄位是同一份原始回應，但這裡要的是「已發行普通股數或TDR原股發行股數」
        欄位（實測已核對：該值＝「實收資本額」÷「普通股每股面額」，即官方揭露的實際流通股數，
        不是用面額 10 元回推的粗略估計）。這裡獨立呼叫一次，不與 industry_fetcher.py 共用同一次
        HTTP 回應：兩者關注點不同（產業標籤 vs 市值計算），各自獨立失敗互不影響，比照全站
        「單一失敗不拖累其他」的既有慣例；t187ap03_L 是輕量、無需金鑰的公開 API，重複呼叫不構成
        實質負擔。

        僅涵蓋一般普通股公司（t187ap03_L 只收錄普通股發行公司，不含 ETF／特別股／TDR 等，這些
        證券本來就沒有「股本」概念，市值計算對它們天生不適用，缺席即缺席）。只做上市（TWSE），
        比照 fetch_twse_valuation() 既有的上市限定範圍——上櫃資料涵蓋是另一個已知缺口
        （docs/16.AI技術分析/Phase2-籌碼面與基本面量化擴充.md §9 Q-2），不在本次修復範圍內。

        回傳 {symbol: shares_outstanding}，個股解析失敗則整檔跳過。"""
        try:
            r = requests.get(SHARES_OUTSTANDING_URL, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                logger.warning(f"[ValuationFetcher] TWSE t187ap03_L HTTP {r.status_code}")
                return {}
            rows = r.json()
            result: Dict[str, int] = {}
            for row in rows:
                symbol = str(row.get("公司代號", "")).strip()
                shares = _clean_shares(row.get("已發行普通股數或TDR原股發行股數"))
                if symbol and shares:
                    result[symbol] = shares
            logger.info(f"[ValuationFetcher] 取得 {len(result)} 檔上市公司已發行股數資料")
            return result
        except Exception as e:
            logger.error(f"[ValuationFetcher] 抓取上市公司已發行股數失敗: {e}")
            return {}

    def _get_shares_outstanding(self) -> Dict[str, int]:
        if self._shares_outstanding_cache is None:
            self._shares_outstanding_cache = self.fetch_tw_shares_outstanding()
        return self._shares_outstanding_cache

    def fetch_twse_valuation(self, trade_date: date) -> List[Dict[str, Any]]:
        """抓取 TWSE 指定日期的個股本益比、殖利率、淨值比、市值與市值排名。

        市值＝當日收盤價（BWIBBU_d 本身就有「收盤價」欄位，不必另外查 daily_stock_data）×
        已發行股數（見 fetch_tw_shares_outstanding()，用目前最新值——歷史回補時嚴格來說會用
        「今天」的股數去乘「過去某天」的股價，對曾經增減資的公司會有誤差，但股本異動頻率遠低於
        股價波動，這是可接受、且已誠實記錄於此的近似）。任一邊缺席（虧損股仍有股價，但無法對應
        股數的證券如 ETF／特別股）則 market_cap 為 None，不得以 0 頂替。
        """
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
            sym_idx, name_idx, price_idx, pe_idx, yield_idx, pb_idx = 0, 1, 2, 2, 3, 4
            for i, f in enumerate(fields):
                if "證券代號" in f or "代號" in f:
                    sym_idx = i
                elif "證券名稱" in f or "名稱" in f:
                    name_idx = i
                elif "收盤價" in f:
                    price_idx = i
                elif "本益比" in f:
                    pe_idx = i
                elif "殖利率" in f:
                    yield_idx = i
                elif "淨值比" in f:
                    pb_idx = i

            shares_map = self._get_shares_outstanding()

            results = []
            for row in raw_data:
                if len(row) <= max(sym_idx, price_idx, pe_idx, yield_idx, pb_idx):
                    continue
                symbol = str(row[sym_idx]).strip()
                # 排除非股票/ETF 的特殊代號若有需要
                if not symbol:
                    continue

                pe = _clean_float(row[pe_idx])
                div_yield = _clean_float(row[yield_idx])
                pb = _clean_float(row[pb_idx])
                close_price = _clean_float(row[price_idx])

                shares = shares_map.get(symbol)
                market_cap = int(round(close_price * shares)) if close_price and shares else None

                results.append({
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "market_type": "tw",
                    "exchange": "TWSE",
                    "pe_ratio": pe,
                    "pb_ratio": pb,
                    "dividend_yield": div_yield,
                    "market_cap": market_cap,
                    "mcap_rank": None,   # 下方統一排名後回填
                    "source": "BWIBBU_d",
                })

            _assign_mcap_rank(results)
            return results
        except Exception as e:
            logger.error(f"[ValuationFetcher] 抓取 TWSE 估值失敗 ({date_str}): {e}")
            return []

    def fetch_twse_valuation_snapshot(self) -> List[Dict[str, Any]]:
        """當日快照備援（BWIBBU_ALL OpenAPI）。

        market_cap／mcap_rank 這裡維持 None，非遺漏：BWIBBU_ALL 只回傳 Code／Name／PEratio／
        DividendYield／PBratio 五個欄位（已實測核對），不像 BWIBBU_d 本身就帶收盤價，這個
        備援來源沒有算市值所需的價格可用，不得臆測。這條路徑本來就只在主來源
        fetch_twse_valuation() 打不到資料時才會被呼叫，市值欄位偶爾缺席的影響有限。"""
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
