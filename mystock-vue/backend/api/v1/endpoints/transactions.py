"""交易紀錄 CRUD ＋ CSV 匯入/匯出（設計文件 §一）。"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date as date_cls, datetime, time as time_cls
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from decimal import Decimal

from core.owner_auth import require_owner
from db.session import get_db
from repositories.exchange_rate_repository import ExchangeRateRepository
from repositories.portfolio_repository import PortfolioRepository
from services import tracking_service
from services.portfolio_ledger import D, Settings, compute_fee, compute_tax, to_float, validate_no_oversell

logger = logging.getLogger("mystock-backend")

router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["Portfolio - Transactions"],
    dependencies=[Depends(require_owner)],
)

CSV_HEADER = ["date", "time", "market", "side", "symbol", "name", "shares", "price", "odd_lot", "fee", "tax"]


class TransactionIn(BaseModel):
    market: str
    symbol: str
    name: Optional[str] = None
    side: str
    trade_date: date_cls
    trade_time: Optional[time_cls] = None
    shares: float
    price: float
    odd_lot: bool = False
    fee: Optional[float] = None   # 提供則視為手動覆寫
    tax: Optional[float] = None
    note: Optional[str] = None


def _tx_out(row: dict, fx_rate: Optional[Decimal] = None) -> dict:
    net = row["price"] * row["shares"] + (row["fee"] + row["tax"]) * (1 if row["side"] == "buy" else -1)
    # 美股「折算台幣」欄位：用交易當天的台灣銀行歷史即期匯率（非記帳設定頁的手動 fx_rate），
    # 查不到歷史匯率（例如尚未爬過那個日期）時維持 None，前端顯示「—」，不用手動值頂替
    # （見 docs/8.個人投資記帳功能/個人投資記帳功能_design.md 補充章節的範圍邊界說明）。
    price_twd = net_twd = None
    if row["market"] == "us" and fx_rate is not None:
        price_twd = to_float(row["price"] * fx_rate)
        net_twd = to_float(net * fx_rate)
    return {
        "id": row["id"], "market": row["market"], "symbol": row["symbol"], "name": row["name"], "side": row["side"],
        "trade_date": row["trade_date"].isoformat(), "trade_time": row["trade_time"].isoformat() if row["trade_time"] else None,
        "shares": to_float(row["shares"]), "price": to_float(row["price"]), "odd_lot": row["odd_lot"],
        "fee": to_float(row["fee"]), "tax": to_float(row["tax"]),
        "fee_is_manual": row["fee_is_manual"], "tax_is_manual": row["tax_is_manual"], "note": row["note"],
        "net": to_float(net),
        "price_twd": price_twd, "net_twd": net_twd,
    }


async def _current_settings(db) -> Settings:
    return Settings.from_row(await PortfolioRepository(db).get_settings())


async def _usd_rate_for(db, trade_date) -> Optional[Decimal]:
    """單筆交易用：create/update 回傳單一列時查一次當天（或最近更早）的美元即期匯率。"""
    return await ExchangeRateRepository(db).get_rate_for_date("USD", trade_date)


async def _usd_rates_for_rows(db, rows: list[dict]) -> dict:
    """清單查詢用：把所有美股交易的交易日彙整成一批唯一日期，各查一次最近可用匯率
    （見 ExchangeRateRepository.get_rates_for_dates 的說明）。"""
    dates = {r["trade_date"] for r in rows if r["market"] == "us"}
    if not dates:
        return {}
    return await ExchangeRateRepository(db).get_rates_for_dates("USD", dates)


def _validate_shape(market: str, side: str, shares: float, price: float, odd_lot: bool) -> None:
    if market not in ("tw", "us"):
        raise HTTPException(400, "market 必須為 tw 或 us")
    if side not in ("buy", "sell"):
        raise HTTPException(400, "side 必須為 buy 或 sell")
    if shares is None or shares <= 0:
        raise HTTPException(400, "股數必須大於 0")
    if price is None or price <= 0:
        raise HTTPException(400, "單價必須大於 0")
    if market == "tw" and not odd_lot and D(shares) % 1000 != 0:
        raise HTTPException(400, "台股整股交易股數需為 1000 的倍數，或標記為零股交易")


async def _prepare_tx_row(payload: TransactionIn, settings: Settings, existing_id: Optional[int] = None) -> dict:
    _validate_shape(payload.market, payload.side, payload.shares, payload.price, payload.odd_lot)
    symbol = payload.symbol.strip().upper()
    shares, price = D(payload.shares), D(payload.price)

    fee = D(payload.fee) if payload.fee is not None else compute_fee(payload.market, symbol, price, shares, settings)
    tax = D(payload.tax) if payload.tax is not None else compute_tax(payload.market, symbol, payload.side, price, shares, settings)

    return {
        "id": existing_id, "market": payload.market, "symbol": symbol, "name": (payload.name or symbol).strip(),
        "side": payload.side, "trade_date": payload.trade_date, "trade_time": payload.trade_time,
        "shares": shares, "price": price, "odd_lot": payload.odd_lot,
        "fee": fee, "tax": tax,
        "fee_is_manual": payload.fee is not None, "tax_is_manual": payload.tax is not None,
        "note": payload.note,
    }


async def _validate_symbol_ledger(
    repo: PortfolioRepository, market: str, symbol: str, candidate: Optional[dict], exclude_id: Optional[int],
) -> None:
    txs = [t for t in await repo.list_transactions_for_symbol(market, symbol) if t["id"] != exclude_id]
    if candidate is not None:
        txs.append(candidate)
    try:
        validate_no_oversell(txs)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("", summary="查詢交易紀錄")
async def list_transactions(
    market: Optional[str] = Query(None), side: Optional[str] = Query(None), keyword: Optional[str] = Query(None),
    date_from: Optional[date_cls] = Query(None), date_to: Optional[date_cls] = Query(None),
    db=Depends(get_db),
):
    rows = await PortfolioRepository(db).list_transactions(market, side, keyword, date_from, date_to)
    fx_by_date = await _usd_rates_for_rows(db, rows)
    return {"success": True, "data": [_tx_out(r, fx_by_date.get(r["trade_date"])) for r in rows], "total": len(rows)}


@router.post("", summary="新增交易紀錄")
async def create_transaction(payload: TransactionIn, db=Depends(get_db)):
    repo = PortfolioRepository(db)
    settings = await _current_settings(db)
    prepared = await _prepare_tx_row(payload, settings)
    await _validate_symbol_ledger(repo, prepared["market"], prepared["symbol"], prepared, exclude_id=None)
    row = await repo.create_transaction({k: v for k, v in prepared.items() if k != "id"})
    fx_rate = await _usd_rate_for(db, row["trade_date"]) if row["market"] == "us" else None

    # 持股自動納入追蹤清單（ADR-08，追蹤與觀察名單整合規劃書 §12）：買賣皆觸發同一 upsert，
    # 已在清單中則不動既有目標價／tag／原因。best-effort──失敗只記警告，不擋交易寫入。
    try:
        await tracking_service.upsert_from_holding(row["market"], row["symbol"], row["name"])
    except Exception as exc:
        logger.warning("[持股連動] 新增交易後 upsert 追蹤清單失敗（market=%s, symbol=%s）：%s", row["market"], row["symbol"], exc)

    return {"success": True, "data": _tx_out(row, fx_rate), "message": "交易紀錄已新增"}


@router.put("/{tx_id}", summary="編輯交易紀錄")
async def update_transaction(tx_id: int, payload: TransactionIn, db=Depends(get_db)):
    repo = PortfolioRepository(db)
    old = await repo.get_transaction(tx_id)
    if not old:
        raise HTTPException(404, "找不到交易紀錄")

    settings = await _current_settings(db)
    prepared = await _prepare_tx_row(payload, settings, existing_id=tx_id)

    if old["market"] != prepared["market"] or old["symbol"] != prepared["symbol"]:
        # 代號/市場被改掉了：確認移出後，原本那檔股票剩餘的交易時間序仍然不會賣超
        await _validate_symbol_ledger(repo, old["market"], old["symbol"], candidate=None, exclude_id=tx_id)
    await _validate_symbol_ledger(repo, prepared["market"], prepared["symbol"], candidate=prepared, exclude_id=tx_id)

    row = await repo.update_transaction(tx_id, {k: v for k, v in prepared.items() if k != "id"})
    fx_rate = await _usd_rate_for(db, row["trade_date"]) if row["market"] == "us" else None
    return {"success": True, "data": _tx_out(row, fx_rate), "message": "交易紀錄已更新"}


@router.delete("/{tx_id}", summary="刪除交易紀錄")
async def delete_transaction(tx_id: int, db=Depends(get_db)):
    repo = PortfolioRepository(db)
    old = await repo.get_transaction(tx_id)
    if not old:
        raise HTTPException(404, "找不到交易紀錄")
    await _validate_symbol_ledger(repo, old["market"], old["symbol"], candidate=None, exclude_id=tx_id)
    await repo.delete_transaction(tx_id)
    return {"success": True, "message": "已刪除交易紀錄"}


# ── CSV 匯入／匯出（設計文件 §一：批次匯入/匯出功能） ────────────────────────
def _parse_csv_rows(raw: str) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    errors: list[dict] = []
    reader = csv.reader(io.StringIO(raw))
    lines = [line for line in reader if any(cell.strip() for cell in line)]
    if not lines:
        return rows, errors
    start = 1 if lines[0] and lines[0][0].strip().lower() == "date" else 0

    for i in range(start, len(lines)):
        line_no = i + 1
        cells = lines[i] + [""] * (len(CSV_HEADER) - len(lines[i]))
        d, t, market, side, symbol, name, shares, price, odd_lot, fee, tax = cells[:11]
        try:
            if not d or not market or not side or not symbol:
                raise ValueError("缺少必填欄位 (date/market/side/symbol)")
            if market not in ("tw", "us"):
                raise ValueError(f"market 需為 tw 或 us，收到「{market}」")
            if side not in ("buy", "sell"):
                raise ValueError(f"side 需為 buy 或 sell，收到「{side}」")
            trade_date = datetime.strptime(d.strip(), "%Y-%m-%d").date()
            trade_time = datetime.strptime(t.strip(), "%H:%M").time() if t.strip() else None
            shares_v, price_v = float(shares), float(price)
            if shares_v <= 0 or price_v <= 0:
                raise ValueError("shares 與 price 必須是大於 0 的數字")
            is_odd = odd_lot.strip() in ("1", "true", "True")
            if market == "tw" and not is_odd and D(shares_v) % 1000 != 0:
                raise ValueError("台股整股需為 1000 股倍數，或將 odd_lot 設為 1")
            rows.append({
                "trade_date": trade_date, "trade_time": trade_time, "market": market, "side": side,
                "symbol": symbol.strip().upper(), "name": (name or symbol).strip(), "shares": shares_v, "price": price_v,
                "odd_lot": is_odd,
                "fee": float(fee) if fee.strip() else None, "tax": float(tax) if tax.strip() else None,
            })
        except (ValueError, TypeError) as exc:
            errors.append({"line": line_no, "message": str(exc)})
    return rows, errors


@router.post("/import", summary="批次匯入交易紀錄（CSV 檔案或純文字）")
async def import_transactions(
    file: Optional[UploadFile] = File(None), csv_text: Optional[str] = Form(None), db=Depends(get_db),
):
    raw = (await file.read()).decode("utf-8-sig") if file is not None else (csv_text or "")
    if not raw.strip():
        raise HTTPException(400, "請提供檔案或 CSV 內容")

    rows, errors = _parse_csv_rows(raw)
    repo = PortfolioRepository(db)
    settings = await _current_settings(db)

    committed = 0
    for row in rows:
        payload = TransactionIn(
            market=row["market"], symbol=row["symbol"], name=row["name"], side=row["side"],
            trade_date=row["trade_date"], trade_time=row["trade_time"], shares=row["shares"], price=row["price"],
            odd_lot=row["odd_lot"], fee=row["fee"], tax=row["tax"],
        )
        try:
            prepared = await _prepare_tx_row(payload, settings)
            await _validate_symbol_ledger(repo, prepared["market"], prepared["symbol"], prepared, exclude_id=None)
        except HTTPException as exc:
            errors.append({"line": None, "message": f"{row['symbol']} {row['trade_date']}：{exc.detail}"})
            continue
        await repo.create_transaction({k: v for k, v in prepared.items() if k != "id"})
        committed += 1

    return {"success": True, "data": {"committed": committed, "errors": errors}, "message": f"已匯入 {committed} 筆"}


@router.get("/export", summary="匯出交易紀錄為 CSV")
async def export_transactions(
    market: Optional[str] = Query(None), side: Optional[str] = Query(None), keyword: Optional[str] = Query(None),
    date_from: Optional[date_cls] = Query(None), date_to: Optional[date_cls] = Query(None),
    db=Depends(get_db),
):
    rows = await PortfolioRepository(db).list_transactions(market, side, keyword, date_from, date_to)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for r in rows:
        writer.writerow([
            r["trade_date"].isoformat(), r["trade_time"].isoformat() if r["trade_time"] else "", r["market"],
            r["side"], r["symbol"], r["name"], to_float(r["shares"]), to_float(r["price"]),
            1 if r["odd_lot"] else 0, to_float(r["fee"]), to_float(r["tax"]),
        ])
    buf.seek(0)
    filename = f"transactions_{date_cls.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
