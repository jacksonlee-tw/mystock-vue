"""全市場資料查詢與抓取 API 端點（選股功能與爬蟲 規格書 §8.4、ADR-SP-14）。"""
import asyncio
import csv
from datetime import date, datetime
import io
import logging
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from config import get_market_manual_backfill_max_days
from repositories.market_repository import MarketRepository, SORT_COLUMN_WHITELIST
from services.market_fetcher import market_fetcher

logger = logging.getLogger("mystock-backend")

router = APIRouter(prefix="/api/v1/market", tags=["Market"])
market_repo = MarketRepository()

# asyncio 只對 Task 持有 weak reference，任務可能在執行中途被 GC 回收（官方文件已警告）；
# 背景抓取動輒跑數十分鐘，這裡另存一份強參照，任務結束時自行從集合移除。
_background_tasks: Set[asyncio.Task] = set()


def _on_background_task_done(task: asyncio.Task) -> None:
    """背景任務結束時卸下強參照，並把例外記錄出來。

    沒人 await 這個 task，例外預設會被完全吞掉（要等 GC 才可能印出 "Task exception was never
    retrieved"），現象就是抓取無聲無息停住、log 什麼都沒有。這裡主動取出例外並記錄。"""
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("[Market] 背景抓取任務異常結束: %s", exc, exc_info=exc)


class MarketFetchRequest(BaseModel):
    start: str = Field(..., description="起始交易日 YYYY-MM-DD")
    end: str = Field(..., description="結束交易日 YYYY-MM-DD")
    targets: Optional[List[str]] = Field(default=["quote", "chip", "valuation"], description="抓取項目")
    throttle_seconds: Optional[int] = Field(default=3, description="節流秒數")


@router.get("/daily")
async def get_market_daily(
    date: Optional[str] = Query(None, description="交易日 YYYY-MM-DD"),
    market: str = Query("tw", description="市場代碼"),
    exchange: Optional[str] = Query(None, description="交易所 TWSE / TPEx"),
    security_type: Optional[str] = Query(None, description="證券類別"),
    industry: Optional[str] = Query(None, description="產業名稱"),
    q: Optional[str] = Query(None, description="代號或名稱搜尋"),
    symbols: Optional[str] = Query(None, description="逗號分隔代號清單"),
    sort: str = Query("turnover", description="排序欄位"),
    order: str = Query("desc", description="排序方向 asc / desc"),
    page: int = Query(1, ge=1, description="頁碼"),
    page_size: int = Query(50, ge=1, le=200, description="每頁筆數"),
    include_delisted: bool = Query(False, description="是否包含下市櫃"),
    include_suspect: bool = Query(False, description="是否包含可疑數據"),
    format: Optional[str] = Query(None, description="匯出格式 csv / json"),
    # 數值篩選
    min_close: Optional[float] = Query(None),
    max_close: Optional[float] = Query(None),
    min_change_percent: Optional[float] = Query(None),
    max_change_percent: Optional[float] = Query(None),
    min_volume: Optional[float] = Query(None),
    max_volume: Optional[float] = Query(None),
    min_turnover: Optional[float] = Query(None),
    max_turnover: Optional[float] = Query(None),
    min_pe_ratio: Optional[float] = Query(None),
    max_pe_ratio: Optional[float] = Query(None),
    min_pb_ratio: Optional[float] = Query(None),
    max_pb_ratio: Optional[float] = Query(None),
    min_dividend_yield: Optional[float] = Query(None),
    max_dividend_yield: Optional[float] = Query(None),
    min_foreign_net: Optional[float] = Query(None),
    max_foreign_net: Optional[float] = Query(None),
    min_trust_net: Optional[float] = Query(None),
    max_trust_net: Optional[float] = Query(None),
    min_institutional_net: Optional[float] = Query(None),
    max_institutional_net: Optional[float] = Query(None),
    min_margin_balance: Optional[float] = Query(None),
    max_margin_balance: Optional[float] = Query(None),
):
    """全市場單日切片資料查詢（支援伺服器端排序、分頁與數值區間篩選）。"""
    if sort not in SORT_COLUMN_WHITELIST:
        raise HTTPException(
            status_code=400,
            detail=f"不合法的排序欄位 '{sort}'。可用欄位包含：{list(SORT_COLUMN_WHITELIST.keys())}",
        )

    t_date = None
    if date:
        try:
            t_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式必須為 YYYY-MM-DD")

    symbols_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else None

    # 組裝數值篩選條件
    num_filters = {}
    if min_close is not None or max_close is not None: num_filters["close"] = (min_close, max_close)
    if min_change_percent is not None or max_change_percent is not None: num_filters["change_percent"] = (min_change_percent, max_change_percent)
    if min_volume is not None or max_volume is not None: num_filters["volume"] = (min_volume, max_volume)
    if min_turnover is not None or max_turnover is not None: num_filters["turnover"] = (min_turnover, max_turnover)
    if min_pe_ratio is not None or max_pe_ratio is not None: num_filters["pe_ratio"] = (min_pe_ratio, max_pe_ratio)
    if min_pb_ratio is not None or max_pb_ratio is not None: num_filters["pb_ratio"] = (min_pb_ratio, max_pb_ratio)
    if min_dividend_yield is not None or max_dividend_yield is not None: num_filters["dividend_yield"] = (min_dividend_yield, max_dividend_yield)
    if min_foreign_net is not None or max_foreign_net is not None: num_filters["foreign_net"] = (min_foreign_net, max_foreign_net)
    if min_trust_net is not None or max_trust_net is not None: num_filters["trust_net"] = (min_trust_net, max_trust_net)
    if min_institutional_net is not None or max_institutional_net is not None: num_filters["institutional_net"] = (min_institutional_net, max_institutional_net)
    if min_margin_balance is not None or max_margin_balance is not None: num_filters["margin_balance"] = (min_margin_balance, max_margin_balance)

    actual_page_size = 5000 if format == "csv" else page_size
    actual_page = 1 if format == "csv" else page

    total, rows, effective_date = await market_repo.query_market_daily(
        trade_date=t_date,
        market=market,
        exchange=exchange,
        security_type=security_type,
        industry=industry,
        q=q,
        symbols=symbols_list,
        num_filters=num_filters,
        sort=sort,
        order=order,
        page=actual_page,
        page_size=actual_page_size,
        include_delisted=include_delisted,
        include_suspect=include_suspect,
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "代號", "名稱", "交易所", "類別", "產業", "開盤", "最高", "最低", "收盤", "漲跌", "漲跌幅%",
            "成交量(股)", "成交金額(元)", "本益比", "股價淨值比", "殖利率%", "市值", "市值排名",
            "外資買賣超(股)", "投信買賣超(股)", "自營商買賣超(股)", "三大法人合計(股)", "融資餘額(張)", "融券餘額(張)"
        ])
        for r in rows:
            writer.writerow([
                r["symbol"], r["name"], r["exchange"], r["security_type"], r["industry"],
                r["open"], r["high"], r["low"], r["close"], r["change_amount"], r["change_percent"],
                r["volume"], r["turnover"], r["pe_ratio"], r["pb_ratio"], r["dividend_yield"],
                r["market_cap"], r["mcap_rank"], r["foreign_net"], r["trust_net"], r["dealer_net"],
                r["institutional_net"], r["margin_balance"], r["short_balance"]
            ])
        csv_bytes = output.getvalue().encode("utf-8-sig")
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=market_{effective_date}.csv"}
        )

    return {
        "success": True,
        "data": {
            "trade_date": str(effective_date) if effective_date else None,
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": rows,
        },
    }


@router.get("/symbols/{symbol}/daily")
async def get_symbol_daily(
    symbol: str,
    start: Optional[str] = Query(None, description="起始日 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="結束日 YYYY-MM-DD"),
    market: str = Query("tw", description="市場代碼"),
):
    """單一標的的全市場期間序列（供個股查詢 Fallback 與圖表使用）。"""
    start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else None
    end_d = datetime.strptime(end, "%Y-%m-%d").date() if end else None

    records = await market_repo.get_symbol_daily_series(
        symbol=symbol,
        start_date=start_d,
        end_date=end_d,
        market=market,
    )
    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "records": records,
        },
    }


@router.get("/dates")
async def get_market_dates(market: str = Query("tw", description="市場代碼")):
    """取得有資料的交易日清單（供前端日期選單）。"""
    dates = await market_repo.get_available_dates(market=market, limit=90)
    return {
        "success": True,
        "data": dates,
    }


@router.get("/status")
async def get_market_status(market: str = Query("tw", description="市場代碼")):
    """全市場資料庫狀態與健康指標。"""
    stats = await market_repo.get_market_status(market=market)
    return {
        "success": True,
        "data": stats,
    }


@router.post("/fetch")
async def trigger_market_fetch(payload: MarketFetchRequest):
    """手動觸發全市場回補與抓取。"""
    try:
        start_d = datetime.strptime(payload.start, "%Y-%m-%d").date()
        end_d = datetime.strptime(payload.end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式必須為 YYYY-MM-DD")

    if start_d > end_d:
        raise HTTPException(status_code=400, detail="起始日期不可大於結束日期")

    max_days = get_market_manual_backfill_max_days()
    if (end_d - start_d).days > max_days * 2:
        raise HTTPException(status_code=400, detail=f"單次補抓範圍過大，請分批在 {max_days} 交易日內進行")

    # 檢查是否有正在執行的 Job
    active = await market_repo.get_active_fetch_job()
    if active:
        raise HTTPException(status_code=409, detail=f"已有全市場作業正在執行中 (ID: {active['id']})")

    # 非阻塞背景執行；保留任務強參照，避免長時間執行中被 GC 回收
    task = asyncio.create_task(
        asyncio.to_thread(
            market_fetcher.backfill_market,
            start_date=start_d,
            end_date=end_d,
            targets=payload.targets or ["quote", "chip", "valuation"],
            throttle_seconds=payload.throttle_seconds or 3,
            trigger_type="manual",
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_on_background_task_done)

    return {
        "success": True,
        "message": f"已啟動全市場抓取作業 ({payload.start} ~ {payload.end})",
    }


@router.post("/fetch/revenue")
async def trigger_market_revenue_fetch():
    """手動觸發全市場最新月營收抓取（monthly_revenue）。

    月營收原本只掛在每月 11 號 09:00 的排程（scheduler.py _scheduled_monthly_revenue），沒有
    手動觸發入口 —— 功能剛上線時或排程當天服務未啟動／執行失敗，都只能乾等到下個月 11 號，
    「營收高成長動能精選」「多因子共振旗艦精選」兩個選股策略也會因此一直是空清單。這裡補上
    一個可重入的手動觸發端點，行為與排程完全相同（見 market_fetcher.fetch_revenue_now()）。
    單次只是一支 TWSE OpenAPI 請求＋一次批次 UPSERT，秒級完成，故不比照 /fetch 走背景任務，
    但仍用 asyncio.to_thread 讓阻塞的 requests 呼叫不卡住主 event loop。"""
    result = await asyncio.to_thread(market_fetcher.fetch_revenue_now, "manual")
    if not result.get("success"):
        return {
            "success": False,
            "error": {"code": "REVENUE_FETCH_EMPTY", "message": "TWSE 月營收 API 未回傳資料，請稍後再試"},
        }
    return {
        "success": True,
        "message": f"已寫入全市場月營收 {result['count']} 筆",
        "data": result,
    }


@router.post("/fetch/cancel")
async def cancel_market_fetch():
    """主動取消正在進行的全市場抓取作業。

    取消旗標只有「這個行程裡真的還活著的工作執行緒」看得到。若 DB 留著 status='running' 但行程
    內沒有對應的工作執行緒（行程重啟或工作執行緒異常結束留下的孤兒），光設旗標永遠沒人理會，
    前端就會一直卡在「進行中」、按取消也沒反應——這種情況直接把該筆紀錄收掉。"""
    active = await market_repo.get_active_fetch_job()
    if not active:
        return {"success": True, "message": "目前沒有進行中的作業"}

    if market_fetcher.active_job_id == active["id"]:
        market_fetcher.request_cancel()
        return {
            "success": True,
            "message": "已發送取消請求，將在完成目前的抓取單元後安全中斷",
        }

    await market_repo.complete_fetch_job(
        active["id"], "interrupted", "作業已無執行中的工作執行緒（殘留紀錄），由使用者手動中止"
    )
    logger.warning("[Market] 作業 %s 無對應的工作執行緒，已直接標記為 interrupted", active["id"])
    return {
        "success": True,
        "message": f"作業 {active['id']} 已無實際執行中的工作，已直接中止並解除鎖定",
    }
