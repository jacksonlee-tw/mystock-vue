from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict, Any, Optional

from markets import get_adapter, MARKETS, resolve_market
from config import get_enabled_markets

router = APIRouter(prefix="/api/v1/markets", tags=["Markets"])

@router.get("", summary="取得啟用的市場清單與其元資料")
def get_markets():
    enabled = get_enabled_markets()
    result = []
    
    for m in enabled:
        try:
            adapter = get_adapter(m)
            result.append({
                "market": m,
                "meta": adapter.meta.__dict__,
                "metrics": [metric.__dict__ for metric in adapter.metrics],
                "session_state": adapter.session_state()
            })
        except ValueError:
            continue
            
    return {"success": True, "data": result}

@router.get("/search", summary="跨市場代號搜尋驗證")
def search_symbols(
    q: str = Query(..., description="搜尋的股票代號，多個以逗號分隔"),
    market: Optional[str] = Query(None, description="指定市場過濾，若無則全部查詢")
):
    symbols = [s.strip() for s in q.split(",") if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="請提供至少一個代號")
        
    enabled = [market] if market and market in MARKETS else get_enabled_markets()
    
    results = {}
    for m in enabled:
        try:
            adapter = get_adapter(m)
            market_results = adapter.validate_symbols(symbols)
            for sym, res in market_results.items():
                if res.get("status") == "resolved":
                    # Keep the first resolved match across markets if not specifying market
                    if sym not in results:
                        results[sym] = res
        except ValueError:
            continue
            
    return {"success": True, "data": results}
