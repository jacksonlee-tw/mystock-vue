from typing import Optional

from fastapi import APIRouter, Query

from strategies.config_loader import load_strategy_config

router = APIRouter(prefix="/api/v1/strategies", tags=["Strategies"])


@router.get("", summary="取得目前生效之策略設定（唯讀，來自 strategy_config/strategies.yaml）")
async def list_strategies(market: Optional[str] = Query(None, description="過濾支援此市場的策略")):
    cfg = load_strategy_config()
    strategies = cfg.strategies
    if market:
        strategies = [s for s in strategies if market in s.markets]

    return {
        "success": True,
        "data": [
            {"id": s.id, "name": s.name, "category": s.category, "enabled": s.enabled, "markets": s.markets}
            for s in strategies
        ],
    }
