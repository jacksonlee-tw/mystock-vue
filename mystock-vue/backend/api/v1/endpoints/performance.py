"""已實現損益與整體績效（設計文件 §三）。"""
from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.owner_auth import require_owner
from db.session import get_db
from repositories.portfolio_repository import PortfolioRepository
from services.portfolio_ledger import (
    D, Settings, build_ledger, compute_irr, compute_twr_approx, summarize_periods, to_float, to_twd,
)

router = APIRouter(
    prefix="/api/v1/performance",
    tags=["Portfolio - Performance"],
    dependencies=[Depends(require_owner)],
)


async def _settings_and_ledger(db, cost_method: Optional[str] = None):
    repo = PortfolioRepository(db)
    settings = Settings.from_row(await repo.get_settings())
    if cost_method in ("fifo", "average"):
        settings.cost_method = cost_method
    transactions = await repo.list_transactions()
    dividends = await repo.list_dividends()
    ledger = build_ledger(transactions, dividends, settings, quotes={})
    return repo, settings, ledger


def _lot_out(lot: dict) -> dict:
    return {
        "id": lot["id"], "close_date": lot["close_date"].isoformat(), "market": lot["market"], "symbol": lot["symbol"],
        "name": lot["name"], "shares": to_float(lot["shares"]), "sell_avg": to_float(lot["sell_avg"]),
        "cost_avg": to_float(lot["cost_avg"]), "cost": to_float(lot["cost"]), "pnl": to_float(lot["pnl"]),
        "pnl_pct": to_float(lot["pnl_pct"]),
        "matches": [
            {
                "buy_date": m["buy_date"].isoformat(), "shares": to_float(m["shares"]),
                "buy_price": to_float(m["buy_price"]), "fee_share": to_float(m["fee_share"]), "pnl": to_float(m["pnl"]),
            }
            for m in lot["matches"]
        ],
    }


@router.get("/realized", summary="已實現損益：平倉明細清單＋統計")
async def get_realized(
    market: Optional[str] = Query(None), cost_method: Optional[str] = Query(None), db=Depends(get_db),
):
    if cost_method not in (None, "fifo", "average"):
        raise HTTPException(400, "cost_method 必須為 fifo 或 average")
    _repo, settings, ledger = await _settings_and_ledger(db, cost_method)

    lots = ledger.realized
    if market:
        lots = [l for l in lots if l["market"] == market]
    dividend_income = ledger.dividend_income
    if market:
        dividend_income = [d for d in dividend_income if d["market"] == market]

    wins = [l for l in lots if l["pnl"] > 0]
    losses = [l for l in lots if l["pnl"] < 0]
    gross_win = sum((to_twd(l["pnl"], l["market"], settings) for l in wins), D(0))
    gross_loss = -sum((to_twd(l["pnl"], l["market"], settings) for l in losses), D(0))
    trade_total = sum((to_twd(l["pnl"], l["market"], settings) for l in lots), D(0))
    dividend_total = sum((to_twd(D(d["amount"]), d["market"], settings) for d in dividend_income), D(0))
    avg_win = gross_win / len(wins) if wins else D(0)
    avg_loss = gross_loss / len(losses) if losses else D(0)

    return {
        "success": True,
        "data": {
            "lots": [_lot_out(l) for l in lots],
            "stats": {
                "lots": len(lots), "wins": len(wins), "losses": len(losses),
                "win_rate": to_float(len(wins) / len(lots) * 100) if lots else 0.0,
                "gross_win": to_float(gross_win), "gross_loss": to_float(gross_loss),
                "avg_win": to_float(avg_win), "avg_loss": to_float(avg_loss),
                "avg_win_loss_ratio": to_float(avg_win / avg_loss) if (wins and losses) else None,
                "trade_total": to_float(trade_total), "dividend_income": to_float(dividend_total),
                "total": to_float(trade_total + dividend_total),
            },
            "cost_method": settings.cost_method,
        },
    }


@router.get("/history", summary="月度／年度已實現損益彙整表")
async def get_history(
    group_by: str = Query("month", description="month 或 year"),
    market: Optional[str] = Query(None), cost_method: Optional[str] = Query(None), db=Depends(get_db),
):
    if group_by not in ("month", "year"):
        raise HTTPException(400, "group_by 必須為 month 或 year")
    if cost_method not in (None, "fifo", "average"):
        raise HTTPException(400, "cost_method 必須為 fifo 或 average")
    _repo, settings, ledger = await _settings_and_ledger(db, cost_method)

    realized = ledger.realized
    dividend_income = ledger.dividend_income
    if market:
        realized = [l for l in realized if l["market"] == market]
        dividend_income = [d for d in dividend_income if d["market"] == market]

    rows = summarize_periods(realized, dividend_income, settings, group_by)
    return {
        "success": True,
        "data": [
            {
                "label": r["label"], "lots": r["lots"], "wins": r["wins"], "losses": r["losses"],
                "win_rate": to_float(r["win_rate"]), "dividend": to_float(r["dividend"]),
                "trade": to_float(r["trade"]), "total": to_float(r["total"]),
            }
            for r in rows
        ],
    }


@router.get("/returns", summary="真實報酬率：TWR（近似）與 IRR")
async def get_returns(db=Depends(get_db)):
    # 沿用 portfolio.py 的 compute_account_state()，帳戶總值/現金餘額算法只有一份，
    # 避免這裡跟 GET /api/v1/portfolio/summary 各自維護一套邏輯而慢慢對不齊。
    from api.v1.endpoints.portfolio import compute_account_state

    state = await compute_account_state(db)
    account_value_twd = to_float(state["account_value_twd"])
    cashflow_rows = [
        {"flow_date": c["flow_date"], "type": c["type"], "amount": to_float(c["amount"])} for c in state["cashflows"]
    ]
    as_of = date_cls.today()

    irr = compute_irr(cashflow_rows, account_value_twd, as_of)
    twr = compute_twr_approx(cashflow_rows, account_value_twd, as_of)

    return {
        "success": True,
        "data": {
            "irr_pct": irr, "twr_pct_approx": twr, "account_value_twd": account_value_twd,
            "note": "TWR 為 Modified Dietz 近似值，正式 TWR 需要每筆外部現金流時點的組合淨值序列（目前無每日淨值快照）",
        },
    }
