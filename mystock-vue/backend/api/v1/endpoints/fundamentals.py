from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from config import get_months_range, get_quarters_range, get_target_stocks
from core.exceptions import SymbolNotFoundException
from services.mops_fetcher import load_stock_revenue, mops_fetch_status, run_fetch_monthly_revenue
from services.mops_eps_fetcher import eps_fetch_status, load_stock_eps, run_fetch_quarterly_eps

router = APIRouter(prefix="/api/v1/fundamentals", tags=["Fundamentals"])


class RevenueFetchTriggerRequest(BaseModel):
    stocks: Optional[List[str]] = None
    months: Optional[int] = None
    force: bool = False


@router.post("/revenue/trigger", summary="觸發月營收抓取任務（背景執行）")
def trigger_revenue_fetch(req: RevenueFetchTriggerRequest, background_tasks: BackgroundTasks):
    snapshot = mops_fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "月營收抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot
        }

    target_stocks = req.stocks if req.stocks else get_target_stocks(market="tw")
    months = req.months if req.months else get_months_range()

    background_tasks.add_task(
        run_fetch_monthly_revenue,
        target_stocks=target_stocks,
        months=months,
        force=req.force,
        trigger_type="manual",
    )
    return {
        "success": True,
        "message": f"已在背景啟動月營收抓取任務 - 目標股票: {target_stocks}, 範圍: 近 {months} 個月",
        "data": mops_fetch_status.get_snapshot()
    }


@router.get("/revenue/status", summary="查詢月營收抓取任務目前進度與日誌")
def get_revenue_fetch_status():
    return {
        "success": True,
        "data": mops_fetch_status.get_snapshot()
    }


@router.get("/revenue/{stock_id}", summary="查詢單一股票的月營收資料")
def get_stock_revenue(stock_id: str):
    data = load_stock_revenue(stock_id)
    if not data:
        raise SymbolNotFoundException(f"找不到股票 {stock_id} 的月營收資料")
    return {
        "success": True,
        "data": data
    }


class EpsFetchTriggerRequest(BaseModel):
    stocks: Optional[List[str]] = None
    quarters: Optional[int] = None
    force: bool = False


@router.post("/eps/trigger", summary="觸發季報 EPS 抓取任務（背景執行）")
def trigger_eps_fetch(req: EpsFetchTriggerRequest, background_tasks: BackgroundTasks):
    snapshot = eps_fetch_status.get_snapshot()
    if snapshot["is_running"]:
        return {
            "success": False,
            "error": {"code": "FETCH_IN_PROGRESS", "message": "季報 EPS 抓取任務已在執行中，請勿重複觸發"},
            "data": snapshot
        }

    target_stocks = req.stocks if req.stocks else get_target_stocks(market="tw")
    quarters = req.quarters if req.quarters else get_quarters_range()

    background_tasks.add_task(
        run_fetch_quarterly_eps,
        target_stocks=target_stocks,
        quarters=quarters,
        force=req.force,
        trigger_type="manual",
    )
    return {
        "success": True,
        "message": f"已在背景啟動季報 EPS 抓取任務 - 目標股票: {target_stocks}, 範圍: 近 {quarters} 季",
        "data": eps_fetch_status.get_snapshot()
    }


@router.get("/eps/status", summary="查詢季報 EPS 抓取任務目前進度與日誌")
def get_eps_fetch_status():
    return {
        "success": True,
        "data": eps_fetch_status.get_snapshot()
    }


@router.get("/eps/{stock_id}", summary="查詢單一股票的季報 EPS 資料")
def get_stock_eps(stock_id: str):
    data = load_stock_eps(stock_id)
    if not data:
        raise SymbolNotFoundException(f"找不到股票 {stock_id} 的季報 EPS 資料")
    return {
        "success": True,
        "data": data
    }


@router.get("/compare", summary="多檔股票基本面與指標綜合比較報表")
async def compare_stocks(
    symbols: str = "",
    market: str = "tw",
):
    """取得多檔股票（最多 10 檔）的行情、估值、營收動能、籌碼與技術面橫向比較數據。"""
    if not symbols:
        return {"success": True, "data": {"symbols": [], "rows": []}}

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:10]
    if not sym_list:
        return {"success": True, "data": {"symbols": [], "rows": []}}

    from datetime import date, timedelta
    from services.chip_provider import ChipDataProvider, MarketPreload
    from repositories.stock_repository import StockRepository
    from repositories.market_repository import MarketRepository
    from indicators.chip import cum_net

    provider = ChipDataProvider()
    stock_repo = StockRepository()
    market_repo = MarketRepository()

    # 批次預載全市場行情／估值／營收（ADR-SP-11：不得為 /compare 另開一套逐檔查詢）
    preload: Optional[MarketPreload] = None
    if market == "tw":
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=120)
            raw_preloaded = await market_repo.preload_market_data(sym_list, start_date, end_date, market=market)
            preload = MarketPreload(
                quotes=raw_preloaded.get("quotes", {}),
                valuation=raw_preloaded.get("valuation", {}),
                revenue=raw_preloaded.get("revenue", {}),
            )
        except Exception:
            preload = None

    rows = []

    for sym in sym_list:
        preload_src = preload if (preload and sym in preload.quotes) else None
        try:
            ctx = await provider.get_bars(
                symbol=sym,
                market=market,
                ma_periods=[5, 20, 60],
                volume_ma_period=5,
                kd_params=[(9, 3, 3)],
                with_valuation=True,
                preloaded=preload_src,
            )
        except Exception:
            ctx = None

        sym_info = await stock_repo.get_symbol(sym)
        name = sym_info.get("name") if sym_info else (ctx.name if ctx else sym)
        exchange = sym_info.get("exchange") if sym_info else "TWSE"

        if not ctx or ctx.length == 0:
            rows.append({
                "symbol": sym,
                "name": name,
                "exchange": exchange,
                "close": None,
                "change_percent": None,
                "volume": None,
                "pe_ratio": None,
                "pb_ratio": None,
                "dividend_yield": None,
                "revenue_yoy": None,
                "revenue_mom": None,
                "foreign_net_5d": None,
                "trust_net_5d": None,
                "ma20": None,
                "bias_ma20": None,
                "kd_k": None,
                "kd_d": None,
            })
            continue

        idx = ctx.length - 1
        last_rec = ctx.raw_records[idx]
        close = ctx.closes[idx]
        change_pct = last_rec.get("change_pct") or last_rec.get("漲跌幅")

        # 估值
        pe = ctx.valuation.get("pe_ratio", [None] * ctx.length)[idx]
        pb = ctx.valuation.get("pb_ratio", [None] * ctx.length)[idx]
        div_yield = ctx.valuation.get("dividend_yield", [None] * ctx.length)[idx]

        # 營收
        rev_yoy = ctx.revenue_yoy[idx] if ctx.revenue_yoy else None
        rev_mom = ctx.revenue_mom[idx] if ctx.revenue_mom else None
        rev_month = ctx.revenue_visible_month[idx] if ctx.revenue_visible_month else None

        # 籌碼 (近 5 日合計張數)
        f_5d = cum_net(ctx.raw_records, "foreign_buy_sell", idx, 5)
        t_5d = cum_net(ctx.raw_records, "trust_buy_sell", idx, 5)

        # 均線與 KD
        ma20 = ctx.ma.get(20, [None] * ctx.length)[idx]
        bias20 = ctx.bias.get(20, [None] * ctx.length)[idx]
        kd_series = ctx.kd.get((9, 3, 3))
        k_val = kd_series.k[idx] if kd_series else None
        d_val = kd_series.d[idx] if kd_series else None

        rows.append({
            "symbol": sym,
            "name": name,
            "exchange": exchange,
            "close": close,
            "change_percent": change_pct,
            "volume": ctx.volumes[idx],
            "turnover": last_rec.get("amount"),
            "pe_ratio": pe,
            "pb_ratio": pb,
            "dividend_yield": div_yield,
            "revenue_yoy": rev_yoy,
            "revenue_mom": rev_mom,
            "revenue_month": rev_month,
            "foreign_net_5d": f_5d,
            "trust_net_5d": t_5d,
            "ma20": ma20,
            "bias_ma20": bias20,
            "kd_k": k_val,
            "kd_d": d_val,
        })

    return {
        "success": True,
        "data": {
            "symbols": sym_list,
            "rows": rows,
        },
    }

