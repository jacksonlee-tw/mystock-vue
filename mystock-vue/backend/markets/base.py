from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

@dataclass
class MarketMeta:
    code: str
    label: str
    exchange: str
    currency: str
    currency_symbol: str
    lot_size: int
    volume_unit_label: str
    amount_unit_label: str
    price_adjusted: bool
    up_down_convention: str
    timezone: str
    panels: List[str] = field(default_factory=list)

@dataclass
class Metric:
    key: str
    label: str
    unit: str
    frequency: str
    markets: List[str] = field(default_factory=list)
    tile: bool = False
    panel: Optional[str] = None
    tone: str = "neutral"

class MarketAdapter(ABC):
    @property
    @abstractmethod
    def meta(self) -> MarketMeta:
        pass
        
    @property
    @abstractmethod
    def metrics(self) -> List[Metric]:
        pass
        
    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """將使用者輸入轉換為標準代號 (例如 '2330.TW' -> '2330')"""
        pass
        
    @abstractmethod
    async def validate_symbols(self, symbols: List[str]) -> Dict[str, Any]:
        """驗證代號並回傳中繼資料，例如名稱、證券類型等。是 async：實作會查詢 Postgres（見
        markets/tw.py／us.py），呼叫端運行在 FastAPI 主 event loop 內，必須直接 await 共用的
        async session，不能透過另開 event loop 的同步橋接（repositories/stock_repository.py
        的 run_async()／dispose_engine() 是為了完全獨立於主程式之外的爬蟲執行緒設計，在還有
        其他併發請求共用同一個 db/session.py 全域 engine 時呼叫會把它們的連線一併弄壞）。"""
        pass

    @abstractmethod
    async def search_symbols(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """依代號前綴或名稱模糊搜尋，回傳建議清單（見自動完成需求），與 validate_symbols()
        的精確驗證用途分工：[{"symbol", "name", "market", "exchange", "security_type"}, ...]。
        同 validate_symbols()，是 async，原因同上。"""
        pass

    @abstractmethod
    def fetch(self, symbols: List[str], days: int) -> Dict[str, Dict[str, Any]]:
        """
        抓取歷史行情與相關籌碼資料，回傳以日期為鍵的資料字典。
        結構: { symbol: { "YYYY-MM-DD": { "close": ..., ... } } }
        """
        pass
        
    @abstractmethod
    def session_state(self) -> str:
        """回傳當前盤況：'open', 'closed', 'after_hours' 等"""
        pass
