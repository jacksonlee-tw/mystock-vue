import asyncio
import logging
import re
import pytz
from typing import List, Dict, Any
from datetime import datetime, time as datetime_time
import yfinance as yf

from .base import MarketAdapter, MarketMeta, Metric

logger = logging.getLogger(__name__)

# symbols 主檔查無資料時（例如尚未同步、或 SEC 清單漏收的極冷門/新上市代碼）才退回逐檔
# 查 yfinance；只對「長得像 ticker」的輸入這麼做，避免使用者打中文名稱時每個按鍵都發一次網路請求。
_TICKER_LIKE = re.compile(r"^[A-Z][A-Z.\-]{0,5}$")

class USMarketAdapter(MarketAdapter):
    @property
    def meta(self) -> MarketMeta:
        return MarketMeta(
            code="us",
            label="美股",
            exchange="US",
            currency="USD",
            currency_symbol="$",
            lot_size=1,
            volume_unit_label="股",
            amount_unit_label="百萬美元",
            price_adjusted=True,
            up_down_convention="green_up",
            timezone="America/New_York",
            panels=["short", "holders", "table"]
        )

    @property
    def metrics(self) -> List[Metric]:
        return [
            Metric(key="short_interest", label="Short Interest", unit="股", frequency="biweekly", markets=["us"], tile=True, panel="short"),
            Metric(key="short_ratio", label="Days to Cover", unit="天", frequency="biweekly", markets=["us"]),
            Metric(key="institutional_holders", label="機構持股", unit="股", frequency="quarterly", markets=["us"], tile=True, panel="holders")
        ]

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper()

    @staticmethod
    def _lookup_yfinance(sym: str) -> Dict[str, Any]:
        """封裝單檔 yfinance 阻塞查詢，供 async 方法透過 asyncio.to_thread 呼叫，
        避免卡住 FastAPI 主 event loop。"""
        try:
            ticker = yf.Ticker(sym)
            info = ticker.info
            name = info.get("shortName") or info.get("longName")
            if name:
                return {
                    "market": "us",
                    "name": name,
                    "exchange": info.get("exchange", "US"),
                    "status": "resolved"
                }
            return {
                "market": "us",
                "status": "not_found",
                "error": "Symbol not found in Yahoo Finance"
            }
        except Exception as e:
            return {
                "market": "us",
                "status": "error",
                "error": str(e)
            }

    async def validate_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        """優先查 symbols 主檔（見 services/symbol_master_fetcher.py 的 SEC EDGAR 同步），
        查無資料的代號才逐檔查 yfinance（較慢，但涵蓋主檔可能漏收的冷門/新上市代碼）。"""
        codes = [self.normalize_symbol(s) for s in symbols]
        found: Dict[str, dict] = {}
        try:
            from repositories.stock_repository import StockRepository

            found = {row["symbol"]: row for row in await StockRepository().get_symbols(codes, "us")}
        except Exception as e:
            logger.warning(f"[美股代號驗證] 查詢 symbols 主檔失敗，全部退回 yfinance 查詢: {e}")

        result = {}
        for sym, code in zip(symbols, codes):
            row = found.get(code)
            if row:
                result[sym] = {
                    "market": "us",
                    "name": row.get("name"),
                    "exchange": row.get("exchange") or "US",
                    "security_type": row.get("security_type"),
                    "status": "resolved",
                }
                continue
            result[sym] = await asyncio.to_thread(self._lookup_yfinance, sym)
        return result

    async def search_symbols(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """優先查 symbols 主檔（代號前綴或公司名稱模糊比對，跟 markets/tw.py 一致）。查無結果、
        且輸入長得像 ticker 時才退回單次 yfinance 驗證（重用 validate_symbols()，不重寫）。"""
        q = query.strip()
        if not q:
            return []

        try:
            from repositories.stock_repository import StockRepository

            rows = await StockRepository().search_symbols(q, "us", limit)
        except Exception as e:
            logger.warning(f"[美股代號搜尋] 查詢 symbols 主檔失敗: {e}")
            rows = []

        if rows:
            return [
                {
                    "symbol": row["symbol"],
                    "name": row.get("name"),
                    "market": "us",
                    "exchange": row.get("exchange") or "US",
                    "security_type": row.get("security_type"),
                }
                for row in rows
            ]

        qu = q.upper()
        if not _TICKER_LIKE.match(qu):
            return []

        info = (await self.validate_symbols([qu])).get(qu, {})
        if info.get("status") != "resolved":
            return []

        return [{
            "symbol": qu,
            "name": info.get("name"),
            "market": "us",
            "exchange": info.get("exchange"),
            "security_type": info.get("security_type"),
        }]

    def fetch(self, symbols: List[str], days: int) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical OHLCV data using yfinance.
        Also fetches short interest and institutional holders.
        """
        quote_lookup = {sym: {} for sym in symbols}
        
        try:
            tickers = yf.Tickers(" ".join(symbols))
            for symbol in symbols:
                ticker = tickers.tickers.get(symbol)
                if not ticker:
                    continue
                    
                period = "3mo" if days <= 90 else "6mo" if days <= 180 else "1y"
                hist = ticker.history(period=period)
                
                if hist.empty:
                    continue
                    
                for date_obj, row in hist.iterrows():
                    date_key = date_obj.strftime("%Y-%m-%d")
                    quote_lookup[symbol][date_key] = {
                        "date": date_key,
                        "symbol": symbol,
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]),
                        "amount": int(row["Volume"] * row["Close"])
                    }
                
                # Fetch static metadata and append to the latest available date
                latest_date = hist.index[-1].strftime("%Y-%m-%d")
                info = ticker.info
                
                # Add short interest
                shares_short = info.get("sharesShort", 0)
                short_ratio = info.get("shortRatio", 0.0)
                
                # Add institutional holders (Total sum)
                inst_holders = 0
                try:
                    holders_df = ticker.institutional_holders
                    if holders_df is not None and not holders_df.empty:
                        # sum up the 'Shares' column
                        inst_holders = int(holders_df["Shares"].sum())
                except Exception:
                    pass
                
                quote_lookup[symbol][latest_date]["short_interest"] = shares_short
                quote_lookup[symbol][latest_date]["short_ratio"] = short_ratio
                quote_lookup[symbol][latest_date]["institutional_holders"] = inst_holders
                quote_lookup[symbol][latest_date]["name"] = info.get("shortName") or info.get("longName", symbol)
                
        except Exception as e:
            logger.error(f"Error fetching quotes from yfinance: {e}")
            
        return quote_lookup
        
    def session_state(self) -> str:
        ny_tz = pytz.timezone(self.meta.timezone)
        now_ny = datetime.now(ny_tz)
        
        if now_ny.weekday() >= 5:
            return "closed"
            
        market_open = datetime_time(9, 30)
        market_close = datetime_time(16, 0)
        
        current_time = now_ny.time()
        
        if current_time < market_open:
            return "pre_market"
        elif current_time > market_close:
            return "after_hours"
        else:
            return "open"
