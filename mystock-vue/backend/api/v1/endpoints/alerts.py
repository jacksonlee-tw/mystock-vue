from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from repositories import alert_repository
from strategies.direction import classify_direction
from strategies.scanner import scan_market

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


class ScanRequest(BaseModel):
    market: str = "tw"
    lookback_days: Optional[int] = None


@router.get("", summary="查詢警示清單")
async def list_alerts(
    market: Optional[str] = Query(None, description="市場代碼過濾 (tw, us)"),
    days: int = Query(7, description="查詢最近幾天"),
    strategy: Optional[str] = Query(None, description="策略 ID 過濾"),
    symbol: Optional[str] = Query(None, description="股票代碼過濾"),
    strength: Optional[str] = Query(None, description="訊號強度過濾: strong/moderate/weak"),
):
    data = alert_repository.query_alerts(
        market=market, days=days, strategy_id=strategy, symbol=symbol, strength=strength
    )
    return {"success": True, "data": data, "total": len(data)}


@router.get("/summary", summary="今日策略摘要")
async def alerts_summary(
    market: Optional[str] = Query(None, description="市場代碼過濾 (tw, us)"),
    date: Optional[str] = Query(None, description="指定日期 YYYY-MM-DD，預設抓資料中最新一天"),
):
    # days 給大一點只是為了「找出目前資料中最新的交易日」，實際統計仍只算 scan_date 當天。
    alerts = alert_repository.query_alerts(market=market, days=3650)
    scan_date = date or (alerts[0]["trade_date"] if alerts else datetime.now().date().isoformat())
    day_alerts = [a for a in alerts if a["trade_date"] == scan_date]

    by_strategy: dict = {}
    by_direction = {"bullish": 0, "bearish": 0}
    for a in day_alerts:
        by_strategy[a["strategy_id"]] = by_strategy.get(a["strategy_id"], 0) + 1
        by_direction[classify_direction(a["direction"])] += 1

    return {
        "success": True,
        "data": {
            "scan_date": scan_date,
            "total_alerts": len(day_alerts),
            "by_strategy": by_strategy,
            "by_direction": by_direction,
        },
    }


@router.post("/scan", summary="手動觸發全市場掃描")
async def trigger_scan(req: ScanRequest):
    if req.market not in ("tw", "us"):
        raise HTTPException(status_code=400, detail="market 必須為 tw 或 us")
    result = await scan_market(req.market, lookback_days=req.lookback_days)
    return {"success": True, "message": "掃描完成", "data": result}
