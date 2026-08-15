"""個人投資記帳帳本引擎（純函式，讀取時重算，不維護 materialized 庫存表）。

Port 自 docs/8.個人投資記帳功能/prototype/index.html 的 buildLedger()/calcFee()/calcTax()/summarize()/
XIRR/Modified-Dietz，邏輯保持一致，但有一個關鍵差異：這裡的 compute_fee()/compute_tax() 只在
「新增交易當下、使用者沒有手動覆寫」時被 repositories/portfolio_repository.py 呼叫一次，算出來的值
會凍結存進 portfolio_transaction.fee/tax；本模組讀到的 transactions 一律已經帶有最終 fee/tax，
不會因為使用者事後調整 portfolio_settings 而讓歷史已實現損益跟著變動（見設計文件 §一）。

成本法（FIFO / 加權平均）與股利處理法（計入收益 / 沖抵成本）則是「分析視角」而非交易當時的事實，
所以維持原型「設定一變，全部歷史重新計算」的行為——由呼叫端把目前 PortfolioSettings 傳進來。

台股 ETF/ETN 稅率判斷沿用 strategies/scanner.py 既有的 _CHIP_EXCLUDED_SYMBOL_PATTERN（^00\\d{2,4}[A-Za-z]?$），
不重複定義正則。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from strategies.scanner import _is_chip_excluded as is_tw_etf_symbol

TW_LOT_SIZE = 1000
ZERO = Decimal("0")
_LATE = time(23, 59, 59)


def D(value: Any) -> Decimal:
    """安全轉 Decimal（None → 0），供組裝 API 輸入時使用。"""
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _round(value: Decimal, exp: str) -> Decimal:
    return value.quantize(Decimal(exp), rounding=ROUND_HALF_UP)


def to_float(value: Any) -> float:
    """Decimal → float，供 API 回應序列化用（比照 db/mapping.py 的既有慣例）。"""
    if value is None:
        return 0.0
    return float(value) if isinstance(value, Decimal) else float(value)


@dataclass
class Settings:
    tw_fee_rate: Decimal = Decimal("0.001425")
    tw_fee_discount: Decimal = Decimal("0.6")
    tw_fee_min: Decimal = Decimal("20")
    tw_tax_rate: Decimal = Decimal("0.003")
    tw_tax_rate_etf: Decimal = Decimal("0.001")
    us_fee_rate: Decimal = Decimal("0")
    us_sec_fee_rate: Decimal = Decimal("0.0000278")
    fx_rate: Decimal = Decimal("32.5")
    cost_method: str = "fifo"          # fifo | average
    dividend_mode: str = "income"      # income | reduce_cost
    near_target_pct: Decimal = Decimal("3")

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "Settings":
        return cls(
            tw_fee_rate=D(row["tw_fee_rate"]), tw_fee_discount=D(row["tw_fee_discount"]),
            tw_fee_min=D(row["tw_fee_min"]), tw_tax_rate=D(row["tw_tax_rate"]),
            tw_tax_rate_etf=D(row["tw_tax_rate_etf"]), us_fee_rate=D(row["us_fee_rate"]),
            us_sec_fee_rate=D(row["us_sec_fee_rate"]), fx_rate=D(row["fx_rate"]),
            cost_method=row["cost_method"], dividend_mode=row["dividend_mode"],
            near_target_pct=D(row["near_target_pct"]),
        )


def to_twd(value: Decimal, market: str, settings: Settings) -> Decimal:
    return value * settings.fx_rate if market == "us" else value


# ══════════════════════════════════════════════════════════════════
# 費用試算（設計文件 §一：自動計算預設費用 + 可設定折讓 + 可手動覆寫）
# 只在新增交易、使用者未手動覆寫時呼叫一次；算出的值之後會凍結存進 DB。
# ══════════════════════════════════════════════════════════════════
def compute_fee(market: str, symbol: str, price: Decimal, shares: Decimal, settings: Settings) -> Decimal:
    gross = price * shares
    if gross <= 0:
        return ZERO
    if market == "tw":
        return max(settings.tw_fee_min, _round(gross * settings.tw_fee_rate * settings.tw_fee_discount, "1"))
    return _round(gross * settings.us_fee_rate, "0.01")


def compute_tax(market: str, symbol: str, side: str, price: Decimal, shares: Decimal, settings: Settings) -> Decimal:
    if side != "sell":
        return ZERO
    gross = price * shares
    if gross <= 0:
        return ZERO
    if market == "tw":
        rate = settings.tw_tax_rate_etf if is_tw_etf_symbol(symbol) else settings.tw_tax_rate
        return _round(gross * rate, "1")
    return _round(gross * settings.us_sec_fee_rate, "0.01")


# ══════════════════════════════════════════════════════════════════
# 賣超防呆：新增/編輯/刪除交易時，針對受影響的 (market, symbol) 重播整條時間序
# ══════════════════════════════════════════════════════════════════
def _tx_sort_key(tx: Dict[str, Any]) -> Tuple[date, time, Any]:
    return (tx["trade_date"], tx.get("trade_time") or _LATE, tx.get("id") if tx.get("id") is not None else math.inf)


def validate_no_oversell(transactions_for_symbol: List[Dict[str, Any]]) -> None:
    """transactions_for_symbol 需為同一個 (market, symbol) 的交易（可含尚未存檔、id=None 的那一筆，
    排序時視為當天最晚）。任何時點賣出後庫存會變負數就拋 ValueError，供 API 層轉成 400。"""
    shares = ZERO
    for tx in sorted(transactions_for_symbol, key=_tx_sort_key):
        qty = D(tx["shares"])
        if tx["side"] == "buy":
            shares += qty
        else:
            shares -= qty
            if shares < 0:
                raise ValueError(
                    f"{tx['trade_date']} 賣出 {qty} 股時庫存不足（當時僅有 {shares + qty} 股），"
                    "請確認交易日期與股數，或先修正/刪除更早的交易紀錄"
                )


# ══════════════════════════════════════════════════════════════════
# 帳本核心：FIFO / 加權平均 → 持股、平倉明細、股利處理
# ══════════════════════════════════════════════════════════════════
@dataclass
class Lot:
    buy_date: date
    shares: Decimal      # 該批次原始股數（配股時可能事後被灌入既有批次，见下方 stock dividend 分支）
    price: Decimal
    fee: Decimal
    remaining: Decimal


@dataclass
class Book:
    market: str
    symbol: str
    name: str
    lots: List[Lot] = field(default_factory=list)
    shares: Decimal = ZERO
    cost: Decimal = ZERO
    dividend_offset: Decimal = ZERO


@dataclass
class LedgerResult:
    positions: List[Dict[str, Any]]
    realized: List[Dict[str, Any]]           # 平倉明細，最新的在前
    dividend_income: List[Dict[str, Any]]    # dividend_mode='income' 時計入已實現的現金股利


def build_ledger(
    transactions: List[Dict[str, Any]],
    dividends: List[Dict[str, Any]],
    settings: Settings,
    quotes: Optional[Dict[Tuple[str, str], Decimal]] = None,
) -> LedgerResult:
    """transactions/dividends 為資料庫列（dict），quotes 為 {(market,symbol): 現價} 供算未實現損益，
    缺現價的標的以 0 帶入（呼叫端負責標示「待報價」，見 api/v1/endpoints/portfolio.py）。"""
    quotes = quotes or {}
    method = settings.cost_method

    events: List[Tuple[date, int, str, Dict[str, Any]]] = []
    for t in transactions:
        events.append((t["trade_date"], t.get("id") or 0, "tx", t))
    for d in dividends:
        # +10_000_000 讓同日的股利排在交易之後（比照原型 10000 + d.id 的排序意圖，數值放大避免與大量交易 id 衝突）
        events.append((d["pay_date"], 10_000_000 + (d.get("id") or 0), "div", d))
    events.sort(key=lambda e: (e[0], e[1]))

    books: Dict[Tuple[str, str], Book] = {}

    def book_of(market: str, symbol: str, name: str) -> Book:
        key = (market, symbol)
        if key not in books:
            books[key] = Book(market=market, symbol=symbol, name=name)
        return books[key]

    realized: List[Dict[str, Any]] = []
    dividend_income: List[Dict[str, Any]] = []
    lot_seq = 1

    for _, _, kind, data in events:
        if kind == "tx":
            t = data
            b = book_of(t["market"], t["symbol"], t["name"])
            shares, price, fee, tax = D(t["shares"]), D(t["price"]), D(t["fee"]), D(t["tax"])
            gross = shares * price

            if t["side"] == "buy":
                b.lots.append(Lot(buy_date=t["trade_date"], shares=shares, price=price, fee=fee, remaining=shares))
                b.shares += shares
                b.cost += gross + fee
            else:
                sell_shares = min(shares, b.shares)
                if sell_shares <= 0:
                    continue  # 理論上已被 validate_no_oversell 擋下，這裡是保險
                sell_proceeds = price * sell_shares - (fee + tax) * (sell_shares / shares)
                cost_basis = ZERO
                matches: List[Dict[str, Any]] = []

                if method == "fifo":
                    need = sell_shares
                    for lot in b.lots:
                        if need <= 0:
                            break
                        if lot.remaining <= 0:
                            continue
                        take = min(lot.remaining, need)
                        fee_share = lot.fee * (take / lot.shares) if lot.shares else ZERO
                        lot_cost = lot.price * take + fee_share
                        cost_basis += lot_cost
                        matches.append({
                            "buy_date": lot.buy_date, "shares": take, "buy_price": lot.price,
                            "fee_share": fee_share,
                            "pnl": (price * take - (fee + tax) * (take / shares)) - lot_cost,
                        })
                        lot.remaining -= take
                        need -= take
                    b.lots = [l for l in b.lots if l.remaining > 0]
                else:
                    cost_basis = b.cost * (sell_shares / b.shares) if b.shares else ZERO

                b.shares -= sell_shares
                if method == "fifo":
                    b.cost = sum(
                        (l.price * l.remaining + (l.fee * (l.remaining / l.shares) if l.shares else ZERO)
                         for l in b.lots), ZERO
                    )
                else:
                    b.cost = max(ZERO, b.cost - cost_basis)
                if b.shares == 0:
                    b.cost = ZERO

                pnl = sell_proceeds - cost_basis
                realized.append({
                    "id": lot_seq, "close_date": t["trade_date"], "market": t["market"], "symbol": t["symbol"],
                    "name": b.name, "shares": sell_shares, "sell_avg": price,
                    "cost_avg": (cost_basis / sell_shares) if sell_shares else ZERO,
                    "cost": (fee + tax) * (sell_shares / shares) + sum((m["fee_share"] for m in matches), ZERO),
                    "pnl": pnl, "pnl_pct": (pnl / cost_basis * 100) if cost_basis else ZERO,
                    "matches": matches,
                })
                lot_seq += 1
        else:
            d = data
            b = book_of(d["market"], d["symbol"], d["name"])
            if d["type"] == "stock":
                extra = D(d["shares"])
                b.shares += extra
                if b.lots:
                    b.lots[-1].remaining += extra
                else:
                    b.lots.append(Lot(buy_date=d["pay_date"], shares=extra, price=ZERO, fee=ZERO, remaining=extra))
            elif settings.dividend_mode == "reduce_cost" and b.shares > 0:
                offset = min(D(d["amount"]), b.cost)
                b.cost -= offset
                b.dividend_offset += offset
                total_remaining = sum((l.remaining for l in b.lots), ZERO) or Decimal("1")
                for l in b.lots:
                    if l.remaining <= 0:
                        continue
                    l.price = max(ZERO, l.price - (offset * (l.remaining / total_remaining)) / l.remaining)
            else:
                dividend_income.append({"date": d["pay_date"], "market": d["market"], "symbol": d["symbol"], "amount": D(d["amount"])})

    positions = []
    for b in books.values():
        if b.shares <= 0:
            continue
        price = quotes.get((b.market, b.symbol), ZERO)
        avg_cost = b.cost / b.shares
        market_value = b.shares * price
        pnl = market_value - b.cost
        positions.append({
            "market": b.market, "symbol": b.symbol, "name": b.name,
            "shares": b.shares, "avg_cost": avg_cost, "price": price, "market_value": market_value,
            "cost": b.cost, "pnl": pnl, "pnl_pct": (pnl / b.cost * 100) if b.cost else ZERO,
            "dividend_offset": b.dividend_offset,
        })
    positions.sort(key=lambda p: p["market_value"], reverse=True)

    return LedgerResult(positions=positions, realized=list(reversed(realized)), dividend_income=dividend_income)


# ══════════════════════════════════════════════════════════════════
# 月度／年度彙整（設計文件 §三）
# ══════════════════════════════════════════════════════════════════
def summarize_periods(
    realized: List[Dict[str, Any]], dividend_income: List[Dict[str, Any]], settings: Settings, granularity: str = "month",
) -> List[Dict[str, Any]]:
    key_of = (lambda d: d.strftime("%Y")) if granularity == "year" else (lambda d: d.strftime("%Y-%m"))
    buckets: Dict[str, Dict[str, Any]] = {}

    def touch(k: str) -> Dict[str, Any]:
        return buckets.setdefault(k, {"label": k, "lots": 0, "wins": 0, "losses": 0, "trade": ZERO, "dividend": ZERO})

    for l in realized:
        b = touch(key_of(l["close_date"]))
        b["lots"] += 1
        if l["pnl"] > 0:
            b["wins"] += 1
        elif l["pnl"] < 0:
            b["losses"] += 1
        b["trade"] += to_twd(l["pnl"], l["market"], settings)

    for d in dividend_income:
        touch(key_of(d["date"]))["dividend"] += to_twd(d["amount"], d["market"], settings)

    rows = []
    for b in buckets.values():
        total = b["trade"] + b["dividend"]
        win_rate = (b["wins"] / b["lots"] * 100) if b["lots"] else 0.0
        rows.append({**b, "total": total, "win_rate": win_rate})
    rows.sort(key=lambda r: r["label"], reverse=True)
    return rows


# ══════════════════════════════════════════════════════════════════
# 報酬率：IRR（XIRR 二分搜尋）／ TWR（Modified Dietz 近似）
# ══════════════════════════════════════════════════════════════════
def _xnpv(rate: float, flows: List[Tuple[date, float]]) -> float:
    t0 = flows[0][0]
    return sum(amount / ((1 + rate) ** ((d - t0).days / 365.0)) for d, amount in flows)


def compute_irr(cashflows: List[Dict[str, Any]], account_value_twd: float, as_of: date) -> Optional[float]:
    """cashflows: [{flow_date, type, amount}]；account_value_twd 為目前帳戶總值（視為 as_of 當天的期末流入）。
    回傳年化 IRR（百分比），無法收斂或現金流方向單一時回傳 None（比照原型行為）。"""
    flows = [(c["flow_date"], -float(c["amount"]) if c["type"] == "deposit" else float(c["amount"])) for c in cashflows]
    flows.sort(key=lambda f: f[0])
    if not flows:
        return None
    flows.append((as_of, account_value_twd))

    if not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        return None

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = _xnpv(lo, flows), _xnpv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _xnpv(mid, flows)
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return ((lo + hi) / 2) * 100


def compute_twr_approx(cashflows: List[Dict[str, Any]], account_value_twd: float, as_of: date) -> float:
    """Modified Dietz 近似值——真正的 TWR 需要每筆外部現金流時點的組合淨值序列（目前沒有每日淨值快照），
    回傳值在 API 層會明確標註為近似（見 docs 原型同一處註解與前端 UI 的『近似值』提示）。"""
    if not cashflows:
        return 0.0
    t0 = min(c["flow_date"] for c in cashflows)
    span_days = max(1, (as_of - t0).days)

    net_flow = 0.0
    weighted = 0.0
    for c in cashflows:
        # 入金為正貢獻、出金為負貢獻（與 IRR 用的號誌相反：那邊是站在投資人口袋看現金流向）
        contribution = float(c["amount"]) if c["type"] == "deposit" else -float(c["amount"])
        net_flow += contribution
        weighted += contribution * ((as_of - c["flow_date"]).days / span_days)

    if weighted == 0:
        return 0.0
    return ((account_value_twd - net_flow) / weighted) * 100
