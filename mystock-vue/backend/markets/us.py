import logging
import pytz
from typing import List, Dict, Any
from datetime import datetime, time as datetime_time
import yfinance as yf

from .base import MarketAdapter, MarketMeta, Metric

logger = logging.getLogger(__name__)

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

    def validate_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        result = {}
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                name = info.get("shortName") or info.get("longName")
                if name:
                    result[sym] = {
                        "market": "us",
                        "name": name,
                        "exchange": info.get("exchange", "US"),
                        "status": "resolved"
                    }
                else:
                    result[sym] = {
                        "market": "us",
                        "status": "not_found",
                        "error": "Symbol not found in Yahoo Finance"
                    }
            except Exception as e:
                result[sym] = {
                    "market": "us",
                    "status": "error",
                    "error": str(e)
                }
        return result
        
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
