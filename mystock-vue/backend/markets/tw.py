from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
import requests
import time

from .base import MarketAdapter, MarketMeta, Metric

FIELD_MAP = {
    "股票名稱": "name", 
    "開盤價": "open", 
    "最高價": "high",
    "最低價": "low", 
    "收盤價": "close",
    "成交股數(股)": "volume", 
    "成交金額(元)": "amount", 
    "成交筆數(筆)": "trades",
    "外資買賣超(張)": "foreign_buy_sell", 
    "投信買賣超(張)": "trust_buy_sell",
    "自營商買賣超(張)": "dealer_buy_sell", 
    "合計買賣超(張)": "institutional_total",
    "估算買賣超金額(萬元)": "institutional_amount_est",
    "融資餘額(張)": "margin_balance", 
    "融券餘額(張)": "short_balance"
}

# The fields returned by TWSE APIs often use Chinese keys
# FIELD_MAP is used during data persistence to standard English keys.

class TaiwanMarketAdapter(MarketAdapter):
    @property
    def meta(self) -> MarketMeta:
        return MarketMeta(
            code="tw",
            label="台股",
            exchange="TWSE",
            currency="TWD",
            currency_symbol="NT$",
            lot_size=1000,
            volume_unit_label="張",
            amount_unit_label="萬元",
            price_adjusted=False,
            up_down_convention="red_up",
            timezone="Asia/Taipei",
            panels=["institutional", "margin", "table"]
        )

    @property
    def metrics(self) -> List[Metric]:
        return [
            Metric(key="foreign_buy_sell", label="外資買賣超", unit="張", frequency="daily", markets=["tw"]),
            Metric(key="trust_buy_sell", label="投信買賣超", unit="張", frequency="daily", markets=["tw"]),
            Metric(key="dealer_buy_sell", label="自營商買賣超", unit="張", frequency="daily", markets=["tw"]),
            Metric(key="institutional_total", label="三大法人合計", unit="張", frequency="daily", markets=["tw"], tile=True, panel="institutional"),
            Metric(key="institutional_amount_est", label="估算買賣超金額", unit="萬元", frequency="daily", markets=["tw"]),
            Metric(key="margin_balance", label="融資餘額", unit="張", frequency="daily", markets=["tw"], tile=True, panel="margin"),
            Metric(key="short_balance", label="融券餘額", unit="張", frequency="daily", markets=["tw"], tile=True, panel="margin")
        ]

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().replace('.TW', '')

    def validate_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        # TODO: Implement actual validation via TWSE API
        # For now, just return a dummy valid response
        result = {}
        for sym in symbols:
            result[sym] = {
                "market": "tw",
                "exchange": "TWSE",
                "security_type": "普通股", # Or ETF depending on symbol format
                "status": "resolved"
            }
        return result
        
    def fetch(self, symbols: List[str], days: int) -> Dict[str, Dict[str, Any]]:
        # The logic will be refactored from fetcher.py in the future
        # For this Phase, we rely on the migration script to rename keys
        # New fetches will use the old fetcher.py logic for now and we'll apply mapping when saving
        pass
        
    def session_state(self) -> str:
        # Determine based on Taiwan time
        return "closed"

