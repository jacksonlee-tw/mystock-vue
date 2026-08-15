"""持股與帳戶總覽（設計文件 §二）＋批次報價輔助端點。"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from db.session import get_db
from repositories.portfolio_repository import PortfolioRepository
from services.portfolio_ledger import D, Settings, build_ledger, to_twd, to_float
from services.stock_service import get_latest_quote

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio - Holdings"])


def _parse_symbol_pairs(raw: str) -> list[tuple[str, str]]:
    pairs = []
    for token in raw.split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        market, symbol = token.split(":", 1)
        market = market.strip().lower()
        symbol = symbol.strip().upper()
        if market in ("tw", "us") and symbol:
            pairs.append((market, symbol))
    return pairs


async def _fetch_quotes(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], Decimal]:
    unique = list(dict.fromkeys(pairs))
    results = await asyncio.gather(*(get_latest_quote(symbol, market) for market, symbol in unique))
    quotes = {}
    for (market, symbol), quote in zip(unique, results):
        if quote is not None:
            quotes[(market, symbol)] = D(quote["close"])
    return quotes


async def _build_ledger_with_quotes(db, cost_method: Optional[str] = None):
    repo = PortfolioRepository(db)
    settings = Settings.from_row(await repo.get_settings())
    if cost_method in ("fifo", "average"):
        settings.cost_method = cost_method

    transactions = await repo.list_transactions()
    dividends = await repo.list_dividends()

    # 先不帶報價算一輪，只為了知道「目前實際有庫存的標的」有哪些，避免對從沒出現過的代號查報價
    draft = build_ledger(transactions, dividends, settings, quotes={})
    pairs = [(p["market"], p["symbol"]) for p in draft.positions]
    quotes = await _fetch_quotes(pairs)

    ledger = build_ledger(transactions, dividends, settings, quotes=quotes)
    return ledger, settings, quotes


def _cash_impact(t: dict) -> Decimal:
    """單筆交易對現金餘額的影響：買進為流出（負），賣出為流入（正）。"""
    gross = D(t["price"]) * D(t["shares"])
    net = gross + D(t["fee"]) + D(t["tax"]) if t["side"] == "buy" else gross - D(t["fee"]) - D(t["tax"])
    return -net if t["side"] == "buy" else net


async def compute_account_state(db, cost_method: Optional[str] = None) -> dict:
    """帳戶總值 = 持股市值＋現金餘額；現金餘額 = 出入金淨額＋交易現金流＋現金股利（不受 dividend_mode
    影響——不管股利記帳上算收益還是沖抵成本，實際入袋的現金一律要算進餘額）。
    供 get_summary() 與 performance.get_returns() 共用，避免現金餘額算法出現兩份不同步的邏輯。"""
    repo = PortfolioRepository(db)
    ledger, settings, quotes = await _build_ledger_with_quotes(db, cost_method)

    portfolio_value_twd = sum((to_twd(p["market_value"], p["market"], settings) for p in ledger.positions), D(0))

    cashflows = await repo.list_cashflows()
    net_cashflow = sum((D(c["amount"]) if c["type"] == "deposit" else -D(c["amount"]) for c in cashflows), D(0))

    dividends = await repo.list_dividends()
    total_cash_dividend_twd = sum(
        (to_twd(D(d["amount"]), d["market"], settings) for d in dividends if d["type"] == "cash"), D(0)
    )

    transactions = await repo.list_transactions()
    traded_twd = sum((to_twd(_cash_impact(t), t["market"], settings) for t in transactions), D(0))

    cash_balance_twd = net_cashflow + traded_twd + total_cash_dividend_twd
    account_value_twd = portfolio_value_twd + cash_balance_twd

    return {
        "repo": repo, "ledger": ledger, "settings": settings, "quotes": quotes,
        "cashflows": cashflows, "portfolio_value_twd": portfolio_value_twd,
        "cash_balance_twd": cash_balance_twd, "account_value_twd": account_value_twd,
    }


def _position_out(p: dict, missing_quote: bool) -> dict:
    return {
        "market": p["market"], "symbol": p["symbol"], "name": p["name"],
        "shares": to_float(p["shares"]), "avg_cost": to_float(p["avg_cost"]), "price": to_float(p["price"]),
        "market_value": to_float(p["market_value"]), "cost": to_float(p["cost"]),
        "pnl": to_float(p["pnl"]), "pnl_pct": to_float(p["pnl_pct"]),
        "dividend_offset": to_float(p["dividend_offset"]), "quote_missing": missing_quote,
    }


@router.get("/quotes", summary="批次取得目前最新收盤價（沿用既有股票資料，不重建報價來源）")
async def get_quotes(symbols: str = Query(..., description="逗號分隔，格式 market:symbol，例如 tw:2330,us:AAPL")):
    pairs = _parse_symbol_pairs(symbols)
    if not pairs:
        raise HTTPException(400, "symbols 需為逗號分隔的 market:symbol 清單，例如 tw:2330,us:AAPL")
    quotes = await _fetch_quotes(pairs)
    data = {f"{m}:{s}": to_float(quotes[(m, s)]) for m, s in pairs if (m, s) in quotes}
    return {"success": True, "data": data}


@router.get("/holdings", summary="目前持股明細（含未實現損益與市值權重）")
async def get_holdings(
    market: Optional[str] = Query(None, description="tw / us，未提供則不篩選"),
    cost_method: Optional[str] = Query(None, description="覆寫設定頁目前的成本法：fifo / average"),
    db=Depends(get_db),
):
    if cost_method not in (None, "fifo", "average"):
        raise HTTPException(400, "cost_method 必須為 fifo 或 average")
    ledger, settings, quotes = await _build_ledger_with_quotes(db, cost_method)

    positions = ledger.positions
    if market:
        positions = [p for p in positions if p["market"] == market]

    total_value_twd = sum((to_twd(p["market_value"], p["market"], settings) for p in positions), D(0))
    out = []
    for p in positions:
        row = _position_out(p, missing_quote=(p["market"], p["symbol"]) not in quotes)
        value_twd = to_twd(p["market_value"], p["market"], settings)
        row["weight_pct"] = to_float(value_twd / total_value_twd * 100) if total_value_twd else 0.0
        out.append(row)

    return {"success": True, "data": out}


@router.get("/summary", summary="儀表板總覽彙總（帳戶總值/未實現損益/已實現損益/勝率）")
async def get_summary(db=Depends(get_db)):
    state = await compute_account_state(db)
    ledger, settings = state["ledger"], state["settings"]
    portfolio_value_twd, cash_balance_twd, account_value_twd = (
        state["portfolio_value_twd"], state["cash_balance_twd"], state["account_value_twd"],
    )

    unrealized_total = sum((to_twd(p["pnl"], p["market"], settings) for p in ledger.positions), D(0))
    unrealized_cost = sum((to_twd(p["cost"], p["market"], settings) for p in ledger.positions), D(0))

    realized = ledger.realized
    wins = [r for r in realized if r["pnl"] > 0]
    losses = [r for r in realized if r["pnl"] < 0]
    trade_total_twd = sum((to_twd(r["pnl"], r["market"], settings) for r in realized), D(0))
    dividend_income_twd = sum((to_twd(D(d["amount"]), d["market"], settings) for d in ledger.dividend_income), D(0))

    return {
        "success": True,
        "data": {
            "account_value_twd": to_float(account_value_twd),
            "portfolio_value_twd": to_float(portfolio_value_twd),
            "cash_balance_twd": to_float(cash_balance_twd),
            "unrealized_total_twd": to_float(unrealized_total),
            "unrealized_total_pct": to_float(unrealized_total / unrealized_cost * 100) if unrealized_cost else 0.0,
            "realized_trade_total_twd": to_float(trade_total_twd),
            "realized_dividend_income_twd": to_float(dividend_income_twd),
            "realized_total_twd": to_float(trade_total_twd + dividend_income_twd),
            "realized_lots": len(realized), "wins": len(wins), "losses": len(losses),
            "win_rate": to_float(len(wins) / len(realized) * 100) if realized else 0.0,
            "cost_method": settings.cost_method,
        },
    }
