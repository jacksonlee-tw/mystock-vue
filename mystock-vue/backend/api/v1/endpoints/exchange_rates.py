"""每日匯率 API（供「股票與爬蟲管理」頁的匯率卡片使用）。見 services/exchange_rate_fetcher.py。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from db.session import get_db
from repositories.exchange_rate_repository import ExchangeRateRepository
from services.portfolio_ledger import to_float

router = APIRouter(prefix="/api/v1/exchange-rates", tags=["Exchange Rates"])


def _rate_out(row: dict) -> dict:
    return {
        "currency": row["currency"], "rate_date": row["rate_date"].isoformat(),
        "rate": to_float(row["rate"]),
        "source": row["source"], "fetched_at": row["fetched_at"].isoformat() if row["fetched_at"] else None,
    }


@router.get("/latest", summary="取得 USD/JPY/CNY 最新一筆每日參考匯率")
async def get_latest(db=Depends(get_db)):
    latest = await ExchangeRateRepository(db).get_latest()
    return {"success": True, "data": {currency: _rate_out(row) for currency, row in latest.items()}}


@router.post("/trigger", summary="立即觸發匯率抓取")
async def trigger_fetch():
    from services.exchange_rate_fetcher import fetch_exchange_rates_async

    # 這個 handler 本身就在 FastAPI 的主 event loop 上執行，用 async 版本直接 await
    # （不能用 fetch_exchange_rates_now()／run_async()，見 exchange_rate_fetcher.py 模組說明——
    # 那個版本會另開一個 event loop，跟主 loop 上其他 DB 操作搶用全域共用的 engine）。
    result = await fetch_exchange_rates_async("manual")
    if not result["success"]:
        return {"success": False, "message": "匯率抓取失敗", "error": {"code": "FETCH_FAILED", "message": result["error"]}}
    return {"success": True, "data": result["data"], "message": f"已更新 {', '.join(result['data']['currencies'])} 匯率"}
