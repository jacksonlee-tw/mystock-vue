"""個人投資記帳模組（portfolio_* 五張表）唯一資料存取入口，API 層不得直接操作 session。

建構子採注入 AsyncSession（比照 repositories/notify_repository.py，配合 api/v1/endpoints 用
`db=Depends(get_db)` 取得請求範圍的 session），查詢則用型別化 ORM `select()`（比照
repositories/stock_repository.py／db/models.py 的風格）——這個新領域沒有同步爬蟲需要橋接
async session 的需求，所以不採 StockRepository 的「每個方法自開 session_factory」寫法。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.portfolio_models import (
    PortfolioCashflow,
    PortfolioDividend,
    PortfolioSettings,
    PortfolioTransaction,
    PortfolioWatchlist,
)


def _tx_to_dict(row: PortfolioTransaction) -> dict:
    return {
        "id": row.id, "market": row.market, "symbol": row.symbol, "name": row.name, "side": row.side,
        "trade_date": row.trade_date, "trade_time": row.trade_time, "shares": row.shares, "price": row.price,
        "odd_lot": row.odd_lot, "fee": row.fee, "tax": row.tax,
        "fee_is_manual": row.fee_is_manual, "tax_is_manual": row.tax_is_manual, "note": row.note,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _dividend_to_dict(row: PortfolioDividend) -> dict:
    return {
        "id": row.id, "market": row.market, "symbol": row.symbol, "name": row.name, "pay_date": row.pay_date,
        "type": row.type, "amount": row.amount, "shares": row.shares, "note": row.note, "created_at": row.created_at,
    }


def _cashflow_to_dict(row: PortfolioCashflow) -> dict:
    return {
        "id": row.id, "flow_date": row.flow_date, "type": row.type, "amount": row.amount,
        "note": row.note, "created_at": row.created_at,
    }


def _watchlist_to_dict(row: PortfolioWatchlist) -> dict:
    return {
        "id": row.id, "market": row.market, "symbol": row.symbol, "name": row.name, "added_date": row.added_date,
        "target_price": row.target_price, "note": row.note, "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _settings_to_dict(row: PortfolioSettings) -> dict:
    return {
        "tw_fee_rate": row.tw_fee_rate, "tw_fee_discount": row.tw_fee_discount, "tw_fee_min": row.tw_fee_min,
        "tw_tax_rate": row.tw_tax_rate, "tw_tax_rate_etf": row.tw_tax_rate_etf, "us_fee_rate": row.us_fee_rate,
        "us_sec_fee_rate": row.us_sec_fee_rate, "fx_rate": row.fx_rate, "cost_method": row.cost_method,
        "dividend_mode": row.dividend_mode, "near_target_pct": row.near_target_pct, "updated_at": row.updated_at,
    }


class PortfolioRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── 交易紀錄 ──────────────────────────────────────────────────────
    async def list_transactions(
        self, market: Optional[str] = None, side: Optional[str] = None, keyword: Optional[str] = None,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
    ) -> list[dict]:
        stmt = select(PortfolioTransaction)
        if market:
            stmt = stmt.where(PortfolioTransaction.market == market)
        if side:
            stmt = stmt.where(PortfolioTransaction.side == side)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where((PortfolioTransaction.symbol.ilike(like)) | (PortfolioTransaction.name.ilike(like)))
        if date_from:
            stmt = stmt.where(PortfolioTransaction.trade_date >= date_from)
        if date_to:
            stmt = stmt.where(PortfolioTransaction.trade_date <= date_to)
        stmt = stmt.order_by(PortfolioTransaction.trade_date, PortfolioTransaction.id)
        result = await self._s.execute(stmt)
        return [_tx_to_dict(r) for r in result.scalars().all()]

    async def list_transactions_for_symbol(self, market: str, symbol: str) -> list[dict]:
        stmt = select(PortfolioTransaction).where(
            PortfolioTransaction.market == market, PortfolioTransaction.symbol == symbol
        ).order_by(PortfolioTransaction.trade_date, PortfolioTransaction.id)
        result = await self._s.execute(stmt)
        return [_tx_to_dict(r) for r in result.scalars().all()]

    async def get_transaction(self, tx_id: int) -> Optional[dict]:
        row = await self._s.get(PortfolioTransaction, tx_id)
        return _tx_to_dict(row) if row else None

    async def create_transaction(self, data: dict) -> dict:
        row = PortfolioTransaction(**data)
        self._s.add(row)
        await self._s.flush()
        return _tx_to_dict(row)

    async def update_transaction(self, tx_id: int, data: dict) -> Optional[dict]:
        row = await self._s.get(PortfolioTransaction, tx_id)
        if not row:
            return None
        for k, v in data.items():
            setattr(row, k, v)
        await self._s.flush()
        return _tx_to_dict(row)

    async def delete_transaction(self, tx_id: int) -> bool:
        row = await self._s.get(PortfolioTransaction, tx_id)
        if not row:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    # ── 股利 ──────────────────────────────────────────────────────────
    async def list_dividends(self, market: Optional[str] = None) -> list[dict]:
        stmt = select(PortfolioDividend)
        if market:
            stmt = stmt.where(PortfolioDividend.market == market)
        stmt = stmt.order_by(PortfolioDividend.pay_date.desc(), PortfolioDividend.id.desc())
        result = await self._s.execute(stmt)
        return [_dividend_to_dict(r) for r in result.scalars().all()]

    async def create_dividend(self, data: dict) -> dict:
        row = PortfolioDividend(**data)
        self._s.add(row)
        await self._s.flush()
        return _dividend_to_dict(row)

    async def delete_dividend(self, dividend_id: int) -> bool:
        row = await self._s.get(PortfolioDividend, dividend_id)
        if not row:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    # ── 出入金 ────────────────────────────────────────────────────────
    async def list_cashflows(self) -> list[dict]:
        stmt = select(PortfolioCashflow).order_by(PortfolioCashflow.flow_date.desc(), PortfolioCashflow.id.desc())
        result = await self._s.execute(stmt)
        return [_cashflow_to_dict(r) for r in result.scalars().all()]

    async def create_cashflow(self, data: dict) -> dict:
        row = PortfolioCashflow(**data)
        self._s.add(row)
        await self._s.flush()
        return _cashflow_to_dict(row)

    async def delete_cashflow(self, cashflow_id: int) -> bool:
        row = await self._s.get(PortfolioCashflow, cashflow_id)
        if not row:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    # ── 觀察名單 ──────────────────────────────────────────────────────
    async def list_watchlist(self, market: Optional[str] = None) -> list[dict]:
        stmt = select(PortfolioWatchlist)
        if market:
            stmt = stmt.where(PortfolioWatchlist.market == market)
        stmt = stmt.order_by(PortfolioWatchlist.added_date.desc(), PortfolioWatchlist.id.desc())
        result = await self._s.execute(stmt)
        return [_watchlist_to_dict(r) for r in result.scalars().all()]

    async def get_watchlist_by_symbol(self, market: str, symbol: str) -> Optional[dict]:
        stmt = select(PortfolioWatchlist).where(
            PortfolioWatchlist.market == market, PortfolioWatchlist.symbol == symbol
        )
        row = (await self._s.execute(stmt)).scalars().first()
        return _watchlist_to_dict(row) if row else None

    async def upsert_watchlist(self, data: dict) -> tuple[dict, bool]:
        """同 (market, symbol) 已存在則更新 target_price/note 並回傳 (row, False)；
        否則新增並回傳 (row, True)（設計文件 §五：重複加入視為更新，不新增重複資料）。"""
        existing = await self.get_watchlist_by_symbol(data["market"], data["symbol"])
        if existing:
            row = await self._s.get(PortfolioWatchlist, existing["id"])
            row.target_price = data["target_price"]
            row.note = data.get("note")
            if data.get("name"):
                row.name = data["name"]
            await self._s.flush()
            return _watchlist_to_dict(row), False
        row = PortfolioWatchlist(**data)
        self._s.add(row)
        await self._s.flush()
        return _watchlist_to_dict(row), True

    async def update_watchlist(self, watch_id: int, data: dict) -> Optional[dict]:
        row = await self._s.get(PortfolioWatchlist, watch_id)
        if not row:
            return None
        for k, v in data.items():
            setattr(row, k, v)
        await self._s.flush()
        return _watchlist_to_dict(row)

    async def delete_watchlist(self, watch_id: int) -> bool:
        row = await self._s.get(PortfolioWatchlist, watch_id)
        if not row:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    # ── 設定（單一列，id=1，由 V8 migration 種好） ─────────────────────
    async def get_settings(self) -> dict:
        row = await self._s.get(PortfolioSettings, 1)
        if not row:
            # 保險：理論上 migration 已種子，若真的沒有就地補一列預設值
            row = PortfolioSettings(id=1)
            self._s.add(row)
            await self._s.flush()
        return _settings_to_dict(row)

    async def update_settings(self, patch: dict) -> dict:
        row = await self._s.get(PortfolioSettings, 1)
        if not row:
            row = PortfolioSettings(id=1)
            self._s.add(row)
        for k, v in patch.items():
            setattr(row, k, v)
        await self._s.flush()
        return _settings_to_dict(row)
