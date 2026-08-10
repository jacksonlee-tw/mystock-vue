from .base import MarketAdapter, MarketMeta, Metric
from .tw import TaiwanMarketAdapter
from .us import USMarketAdapter

MARKETS: dict[str, MarketAdapter] = {
    "tw": TaiwanMarketAdapter(),
    "us": USMarketAdapter()
}

def get_adapter(market: str) -> MarketAdapter:
    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}")
    return MARKETS[market]

def resolve_market(symbol: str, hint: str = None) -> str:
    """
    判定順序：URL／API 明示的 hint → _symbols.json 索引 → symbol_pattern 正則推斷 → 預設 tw。
    暫時簡單實作。
    """
    if hint and hint in MARKETS:
        return hint
        
    # fallback default
    return "tw"
