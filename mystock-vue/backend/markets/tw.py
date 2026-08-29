from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging
import os
import requests
import time

from .base import MarketAdapter, MarketMeta, Metric

logger = logging.getLogger("mystock-backend")

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
            panels=["institutional", "margin", "valuation", "fundamental", "table"]
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
            Metric(key="short_balance", label="融券餘額", unit="張", frequency="daily", markets=["tw"], tile=True, panel="margin"),
            Metric(key="pe_ratio", label="本益比", unit="倍", frequency="daily", markets=["tw"], tile=True, panel="valuation"),
            Metric(key="pb_ratio", label="股價淨值比", unit="倍", frequency="daily", markets=["tw"], tile=True, panel="valuation"),
            Metric(key="dividend_yield", label="殖利率", unit="%", frequency="daily", markets=["tw"], tile=True, panel="valuation"),
            # 市值原始值為「元」（台積電量級約 10^13），直接顯示會是一長串數字，換算成「億元」放後端做
            # （Phase2-籌碼面與基本面量化擴充 設計文件 FR-1、ADR-P2-06：避免前端各處各自硬編碼除數）。
            Metric(key="market_cap", label="市值", unit="億元", frequency="daily", markets=["tw"], tile=True, panel="valuation"),
            Metric(key="mcap_rank", label="市值排名", unit="名", frequency="daily", markets=["tw"], tile=True, panel="valuation"),
            # 月營收（FR-2）：MOPS 每月約 10 日前後才公告上月數字，個股頁副標會標示實際資料月份
            # （見 StockDashboard.vue revenue_visible_month 的顯示邏輯），避免使用者誤以為是當月數字。
            Metric(key="revenue_yoy", label="營收年增率", unit="%", frequency="monthly", markets=["tw"], tile=True, panel="fundamental"),
            Metric(key="revenue_mom", label="營收月增率", unit="%", frequency="monthly", markets=["tw"], tile=True, panel="fundamental"),
        ]

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().replace('.TW', '')

    async def validate_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        """精確驗證代號是否存在於 symbols 主檔（見 services/symbol_master_fetcher.py）並回傳名稱等
        中繼資料。查詢失敗（例如 Postgres 未啟動、主檔尚未同步）時退回「全部視為已知」的舊行為，
        不阻斷新增追蹤等既有流程（見 industry_fetcher.py 開頭「誠實標示資料缺口，不阻斷流程」的原則）。"""
        codes = [self.normalize_symbol(s) for s in symbols]
        try:
            from repositories.stock_repository import StockRepository

            found = {row["symbol"]: row for row in await StockRepository().get_symbols(codes, "tw")}
        except Exception as e:
            logger.warning(f"[台股代號驗證] 查詢 symbols 主檔失敗，退回未驗證狀態: {e}")
            return {
                sym: {"market": "tw", "exchange": "TWSE", "security_type": "普通股", "status": "resolved"}
                for sym in symbols
            }

        result = {}
        for sym, code in zip(symbols, codes):
            row = found.get(code)
            if row:
                result[sym] = {
                    "market": "tw",
                    "name": row.get("name"),
                    "exchange": row.get("exchange") or "TWSE",
                    "security_type": row.get("security_type") or "普通股",
                    "status": "resolved",
                }
            else:
                result[sym] = {"market": "tw", "status": "not_found"}
        return result

    async def search_symbols(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """代號前綴或名稱模糊搜尋（自動完成），查 symbols 主檔。查詢失敗時回傳空清單，
        讓呼叫端（Omnibox／股票管理頁自動完成）優雅降級成「查無建議」而非整頁出錯。"""
        try:
            from repositories.stock_repository import StockRepository

            rows = await StockRepository().search_symbols(query, "tw", limit)
        except Exception as e:
            logger.warning(f"[台股代號搜尋] 查詢 symbols 主檔失敗: {e}")
            return []

        return [
            {
                "symbol": row["symbol"],
                "name": row.get("name"),
                "market": "tw",
                "exchange": row.get("exchange") or "TWSE",
                "security_type": row.get("security_type"),
            }
            for row in rows
        ]

    def fetch(self, symbols: List[str], days: int) -> Dict[str, Dict[str, Any]]:
        # The logic will be refactored from fetcher.py in the future
        # For this Phase, we rely on the migration script to rename keys
        # New fetches will use the old fetcher.py logic for now and we'll apply mapping when saving
        pass
        
    def session_state(self) -> str:
        # Determine based on Taiwan time
        return "closed"

