"""全市場代碼／名稱主檔同步（見 docs/8.個人投資記帳功能 相關的股票代號自動完成需求）。

台股來源改用 TWSE／TPEx 的 ISIN 編碼網頁（C_public.jsp），而非 services/industry_fetcher.py 用的
「公司基本資料」OpenAPI（t187ap03_L / mopsfin_t187ap03_O）——ISIN 頁面涵蓋全部證券類型（含 ETF、
特別股、TDR、受益證券等，公司基本資料只有普通股公司），且不依賴「當天有成交」，是更完整、更穩定
的主檔來源。權證（認購/認售權證）數量龐大（單一市場常上萬檔）、存續期短，不是使用者會手動追蹤的
標的，會嚴重稀釋自動完成建議的可用性，因此明確排除。

美股來源用 SEC EDGAR 官方公開清單（company_tickers_exchange.json），涵蓋美股在 SEC 掛牌申報的
全部代碼與公司名稱，單次 GET 即可取得全市場資料，不需要逐檔查 yfinance。SEC 規定請求需帶可識別的
User-Agent（見 _SEC_HEADERS）。SEC 名單以美國國內申報公司為主，可能漏掉極少數未在 SEC 掛牌的
ADR／新上市代碼，因此 markets/us.py 的 validate_symbols()／search_symbols() 仍保留 yfinance
即時查詢作為主檔查無資料時的備援，不會因為主檔漏掉冷門代碼就整個查不到。

儲存：純 Postgres（repositories/stock_repository.py 的 upsert_symbols_bulk()），不落 JSON——
這是參考／查找用的主檔，不是 OHLC 時序資料，不需要比照 fetcher.py 那套「JSON 為主、Postgres
best-effort 雙寫」的語意（見 CLAUDE.md）。單一來源失敗只記警告，不拋例外給呼叫端。

sync_tw_symbol_master()／sync_us_symbol_master() 刻意是 async（而非比照 industry_fetcher.py 用
run_async() 的同步橋接）：這兩支是從 api/v1/endpoints/stocks.py 的 BackgroundTasks 呼叫，運行在
FastAPI 主 event loop 內，跟 Depends(get_db) 系列端點共用同一個 db/session.py 全域 engine；
run_async() 的「開新 loop、用完 dispose_engine()」設計是為了 fetcher.py/us_fetcher.py 那種完全
獨立於主程式之外的爬蟲執行緒（見該函式的說明），若在主 loop 內呼叫，dispose_engine() 會把其他
併發請求正在用的連線池一併關掉，導致 asyncpg「attached to a different loop」錯亂。爬網部分
(requests，會阻塞) 丟進 asyncio.to_thread 執行，寫入部分直接 await 主 loop 的 async session。
"""
import asyncio
import logging
from typing import Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("mystock-backend")

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_REQUEST_TIMEOUT = 20

# ── 台股：TWSE／TPEx ISIN 編碼網頁 ──────────────────────────────────────
_TW_ISIN_SOURCES = (
    ("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", "TWSE"),  # 上市
    ("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", "TPEx"),  # 上櫃
)
# 排除認購/認售權證：數量龐大（常上萬檔）、存續期短，不是使用者會手動追蹤的標的
_TW_EXCLUDED_SECURITY_TYPES_CONTAINS = ("權證",)


def _parse_tw_isin_table(html: str) -> list[dict]:
    """解析 ISIN 頁面的單一 HTML table：資料列前會穿插「分類列」(colspan，只有一個 td，
    例如「股票」「ETF」「上市認購(售)權證」) 標出後續資料列的證券類型，需要邊掃邊記目前分類。"""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    current_type = None
    results = []
    for tr in rows[1:]:  # 第一列是欄位標題列
        cells = tr.find_all("td")
        if len(cells) == 1:
            current_type = cells[0].get_text(strip=True)
            continue
        if len(cells) < 7:
            continue

        code_name = cells[0].get_text(strip=True)
        parts = code_name.split()  # 代號與名稱間是全形空白，split() 預設就會處理
        if len(parts) < 2:
            continue
        symbol, name = parts[0].strip(), "".join(parts[1:]).strip()
        if not symbol or not name:
            continue
        if current_type and any(kw in current_type for kw in _TW_EXCLUDED_SECURITY_TYPES_CONTAINS):
            continue

        results.append({"symbol": symbol, "name": name, "security_type": current_type})

    return results


def fetch_tw_symbol_master() -> Dict[str, dict]:
    """一次抓全市場（上市＋上櫃）目前有效掛牌的證券代碼與名稱（排除權證）。
    回傳 {symbol: {name, exchange, security_type}}。"""
    result: Dict[str, dict] = {}

    for url, exchange in _TW_ISIN_SOURCES:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
            resp.encoding = "big5"
            rows = _parse_tw_isin_table(resp.text)
            for row in rows:
                result[row["symbol"]] = {
                    "name": row["name"],
                    "exchange": exchange,
                    "security_type": row["security_type"],
                }
            logger.info(f"[代碼主檔] {exchange} 取得 {len(rows)} 檔代碼/名稱資料")
        except Exception as e:
            logger.warning(f"[代碼主檔] {exchange} 代碼清單抓取失敗: {e}")

    return result


async def sync_tw_symbol_master() -> int:
    """更新台股全市場代碼主檔（symbols 表）。回傳更新筆數。"""
    fetched = await asyncio.to_thread(fetch_tw_symbol_master)
    if not fetched:
        logger.warning("[代碼主檔] 台股代碼清單抓取結果為空，本次不更新")
        return 0

    rows = [
        {
            "symbol": symbol,
            "market_type": "tw",
            "name": v["name"],
            "exchange": v["exchange"],
            "status": "active",
        }
        for symbol, v in fetched.items()
    ]
    return await _upsert(rows)


# ── 美股：SEC EDGAR 官方代碼清單 ────────────────────────────────────────
_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
# SEC 規定請求需帶可識別身分的 User-Agent（格式建議：應用名稱 + 聯絡方式），否則可能被拒絕
_SEC_HEADERS = {"User-Agent": "MyStockApp admin@myinvestmentapp.com"}


def fetch_us_symbol_master() -> Dict[str, dict]:
    """SEC EDGAR 公開清單：單次 GET 取得全部在 SEC 申報的美股代碼與公司名稱、交易所。
    回傳 {symbol: {name, exchange}}。"""
    try:
        resp = requests.get(_SEC_TICKERS_URL, headers=_SEC_HEADERS, timeout=_REQUEST_TIMEOUT)
        payload = resp.json()
        fields = payload["fields"]
        idx = {f: i for i, f in enumerate(fields)}

        result: Dict[str, dict] = {}
        for row in payload["data"]:
            symbol = str(row[idx["ticker"]]).strip().upper()
            name = str(row[idx["name"]]).strip()
            exchange = str(row[idx.get("exchange", -1)] or "").strip() if "exchange" in idx else ""
            if not symbol or not name:
                continue
            result[symbol] = {"name": name, "exchange": exchange or None}
        logger.info(f"[代碼主檔] SEC EDGAR 取得 {len(result)} 檔美股代碼/名稱資料")
        return result
    except Exception as e:
        logger.warning(f"[代碼主檔] SEC EDGAR 美股代碼清單抓取失敗: {e}")
        return {}


async def sync_us_symbol_master() -> int:
    """更新美股全市場代碼主檔（symbols 表）。回傳更新筆數。"""
    fetched = await asyncio.to_thread(fetch_us_symbol_master)
    if not fetched:
        logger.warning("[代碼主檔] 美股代碼清單抓取結果為空，本次不更新")
        return 0

    rows = [
        {
            "symbol": symbol,
            "market_type": "us",
            "name": v["name"],
            "exchange": v["exchange"],
            "status": "active",
        }
        for symbol, v in fetched.items()
    ]
    return await _upsert(rows)


async def _upsert(rows: list[dict]) -> int:
    try:
        from repositories.stock_repository import StockRepository

        await StockRepository().upsert_symbols_bulk(rows)
    except Exception as e:
        logger.warning(f"[代碼主檔] 代碼清單寫入 PostgreSQL 失敗: {e}")
        return 0
    return len(rows)
