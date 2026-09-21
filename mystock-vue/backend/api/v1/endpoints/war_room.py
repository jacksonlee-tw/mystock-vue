"""
api/v1/endpoints/war_room.py
Phase5-三層式 AI 決策引擎與戰情室.md FR-5.5：戰情室彙總儀表板的批次查詢端點。獨立成檔而非塞進
ai_analysis.py，因為這裡組合的是「監控清單 × 當日最新 AI 報告」，資料來源橫跨 watchlist 與
ai_analysis_report 兩個既有領域，語意上是一個複合視圖，不是單純的 AI 報告 CRUD。

掛 require_owner（比照既有 watchlist 路由）：戰情室的內容就是監控清單本身，不像
IndustryChainView.vue 只是「標註哪些節點在清單內」的次要裝飾，watchlist 讀取失敗這裡沒有
「優雅降級」的空間，因此不比照 industry_chains 路由的匿名讀取，直接要求 owner 登入。
"""
from __future__ import annotations
from datetime import date, timedelta

from fastapi import APIRouter, Depends

from ai import config as ai_config
from core.owner_auth import require_owner
from db.session import get_db
from repositories.ai_report_repository import AIReportRepository
from services import tracking_service

router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI Analysis - War Room"],
    dependencies=[Depends(require_owner)],
)

# 往回找最新報告的天數上界。報告的 trade_date 是行情最新交易日而非 date.today()——週末、
# 連假沒有新交易日，美股批次在台灣時間清晨跑完時對應的也是前一個美股交易日。只比對「今天」
# 會讓戰情室在這些情境整頁顯示「尚未產生」。給一個有界的回看窗（連假最長約 6 天）：既能涵蓋
# 正常的休市，又不會把半個月前的舊報告當成最新結果端上來；每一列都會回傳自己的 trade_date，
# 由前端如實呈現是哪一天的判讀。
_LOOKBACK_DAYS = 7


def _not_generated_reason(symbol: str, market: str, security_type_map: dict) -> str:
    """批次的逐檔略過原因只存在於當次執行的回傳值與日誌裡（ai/batch_job.py），不落地成可查詢的
    紀錄——這裡只能重新判斷「這檔是否本來就被 ETF 排除」這個確定性規則；其餘原因（配額用盡、
    尚未輪到、產生失敗）在批次跑完後已無從精確區分，一律給一個誠實的通用說明，不假裝知道
    實際原因。"""
    if market == "tw" and ai_config.get_batch_exclude_etf():
        from strategies.scanner import is_chip_excluded
        if is_chip_excluded(symbol, security_type_map.get(symbol)):
            return "ETF／ETN 已排除批次分析（可在個股頁手動點擊產生）"
    return "尚未產生（可能尚未輪到排程、當日配額已用盡，或產生失敗，可手動點擊或等待下次排程）"


@router.get("/war-room", summary="戰情室彙總：監控清單 × 當日最新 AI 報告（一次查完，避免 N+1）")
async def get_war_room(market: str = "tw", db=Depends(get_db)):
    items = await tracking_service.list_items(market=market, crawl_only=True)
    symbols = [it["symbol"] for it in items]

    since_date = date.today() - timedelta(days=_LOOKBACK_DAYS)
    reports = await AIReportRepository(db).list_latest_for_symbols(symbols, market, since_date)

    security_type_map = {}
    if market == "tw":
        from repositories.stock_repository import StockRepository
        rows = await StockRepository().list_symbols(market_type=market)
        security_type_map = {r["symbol"]: r.get("security_type") for r in rows}

    rows = []
    for it in items:
        symbol = it["symbol"]
        report = reports.get(symbol)
        if report:
            target_price = report.get("target_price")
            stop_loss = report.get("stop_loss")
            close = ((report.get("quant_summary") or {}).get("latest") or {}).get("close")
            is_price_hit = close is not None and (
                (stop_loss is not None and close <= stop_loss)
                or (target_price is not None and close >= target_price)
            )
            rows.append({
                "market": market,
                "symbol": symbol,
                "stock_name": it.get("name") or report.get("stock_name"),
                "status": "generated",
                "verdict": report.get("verdict"),
                "headline": report.get("headline"),
                "target_price": target_price,
                "stop_loss": stop_loss,
                "close": close,
                "is_price_hit": is_price_hit,
                "confidence": report.get("confidence"),
                "rule_signal_alignment": report.get("rule_signal_alignment"),
                "trigger_type": report.get("trigger_type"),
                "trade_date": report["trade_date"].isoformat() if report.get("trade_date") else None,
                "generated_at": report.get("generated_at").isoformat() if report.get("generated_at") else None,
                "report_id": report.get("id"),
            })
        else:
            rows.append({
                "market": market,
                "symbol": symbol,
                "stock_name": it.get("name"),
                "status": "not_generated",
                "reason": _not_generated_reason(symbol, market, security_type_map),
                "verdict": None, "headline": None, "target_price": None, "stop_loss": None,
                "close": None, "is_price_hit": False,
                "confidence": None, "rule_signal_alignment": None, "trigger_type": None,
                "trade_date": None, "generated_at": None, "report_id": None,
            })

    # trade_date 回傳「這批報告實際對應的最新交易日」而不是 date.today()：兩者在週末、連假與
    # 美股時差下並不相同，畫面上必須誠實顯示這份總覽是哪一天的判讀（見 _LOOKBACK_DAYS 說明）。
    report_dates = [r["trade_date"] for r in rows if r.get("trade_date")]
    return {
        "success": True,
        "data": {
            "market": market,
            "trade_date": max(report_dates) if report_dates else None,
            "total": len(rows),
            "generated_count": sum(1 for r in rows if r["status"] == "generated"),
            "items": rows,
        },
    }
