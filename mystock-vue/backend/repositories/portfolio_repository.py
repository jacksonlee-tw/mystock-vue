"""個人投資記帳模組（portfolio_* 五張表）唯一資料存取入口，API 層不得直接操作 session。

建構子採注入 AsyncSession（比照 repositories/notify_repository.py，配合 api/v1/endpoints 用
`db=Depends(get_db)` 取得請求範圍的 session），查詢則用型別化 ORM `select()`（比照
repositories/stock_repository.py／db/models.py 的風格）——這個新領域沒有同步爬蟲需要橋接
async session 的需求，所以不採 StockRepository 的「每個方法自開 session_factory」寫法。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.portfolio_models import (
    PortfolioCashflow,
    PortfolioDividend,
    PortfolioSettings,
    PortfolioTransaction,
    PortfolioWatchlist,
    WatchlistItemTag,
    WatchlistTag,
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


def _watchlist_to_dict(row: PortfolioWatchlist, tags: Optional[list[dict]] = None) -> dict:
    return {
        "id": row.id, "market": row.market, "symbol": row.symbol, "name": row.name, "added_date": row.added_date,
        "target_price": row.target_price, "note": row.note, "is_crawl_enabled": row.is_crawl_enabled,
        "source": row.source, "tags": tags or [],
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _tag_to_dict(row: WatchlistTag, usage_count: Optional[int] = None) -> dict:
    out = {"id": row.id, "name": row.name, "color": row.color, "sort_order": row.sort_order}
    if usage_count is not None:
        out["usage_count"] = usage_count
    return out


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

    # ── 追蹤與觀察名單（見 docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §4-5）──────
    async def _load_tags_for(self, watchlist_ids: list[int]) -> dict[int, list[dict]]:
        """批次撈多個清單項目的 tag，避免逐筆各查一次（N+1）。"""
        if not watchlist_ids:
            return {}
        stmt = (
            select(WatchlistItemTag.watchlist_id, WatchlistTag)
            .join(WatchlistTag, WatchlistTag.id == WatchlistItemTag.tag_id)
            .where(WatchlistItemTag.watchlist_id.in_(watchlist_ids))
            .order_by(WatchlistTag.sort_order, WatchlistTag.name)
        )
        result = await self._s.execute(stmt)
        out: dict[int, list[dict]] = {}
        for wid, tag in result.all():
            out.setdefault(wid, []).append(_tag_to_dict(tag))
        return out

    async def list_watchlist(
        self, market: Optional[str] = None, *, tag_ids: Optional[list[int]] = None,
        keyword: Optional[str] = None, has_target: Optional[bool] = None,
        crawl_only: Optional[bool] = None,
    ) -> list[dict]:
        stmt = select(PortfolioWatchlist)
        if market:
            stmt = stmt.where(PortfolioWatchlist.market == market)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where((PortfolioWatchlist.symbol.ilike(like)) | (PortfolioWatchlist.name.ilike(like)))
        if has_target is True:
            stmt = stmt.where(PortfolioWatchlist.target_price.is_not(None))
        elif has_target is False:
            stmt = stmt.where(PortfolioWatchlist.target_price.is_(None))
        if crawl_only:
            stmt = stmt.where(PortfolioWatchlist.is_crawl_enabled.is_(True))
        if tag_ids:
            # 多選 tag 為 AND 語意：必須同時擁有全部指定 tag 才算符合
            sub = (
                select(WatchlistItemTag.watchlist_id)
                .where(WatchlistItemTag.tag_id.in_(tag_ids))
                .group_by(WatchlistItemTag.watchlist_id)
                .having(func.count(func.distinct(WatchlistItemTag.tag_id)) == len(set(tag_ids)))
            )
            stmt = stmt.where(PortfolioWatchlist.id.in_(sub))
        stmt = stmt.order_by(PortfolioWatchlist.added_date.desc(), PortfolioWatchlist.id.desc())
        rows = (await self._s.execute(stmt)).scalars().all()
        tags_by_item = await self._load_tags_for([r.id for r in rows])
        return [_watchlist_to_dict(r, tags_by_item.get(r.id)) for r in rows]

    async def _get_watchlist_row(self, market: str, symbol: str) -> Optional[PortfolioWatchlist]:
        stmt = select(PortfolioWatchlist).where(
            PortfolioWatchlist.market == market, PortfolioWatchlist.symbol == symbol
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def get_watchlist_by_symbol(self, market: str, symbol: str) -> Optional[dict]:
        row = await self._get_watchlist_row(market, symbol)
        if not row:
            return None
        tags = await self._load_tags_for([row.id])
        return _watchlist_to_dict(row, tags.get(row.id))

    async def get_watchlist_by_id(self, watch_id: int) -> Optional[dict]:
        row = await self._s.get(PortfolioWatchlist, watch_id)
        if not row:
            return None
        tags = await self._load_tags_for([row.id])
        return _watchlist_to_dict(row, tags.get(row.id))

    async def upsert_watchlist(self, data: dict) -> tuple[dict, bool]:
        """同 (market, symbol) 已存在則「部分更新」──只覆寫 data 中實際帶到的欄位，回傳 (row, False)；
        否則新增並回傳 (row, True)（設計文件 §五：重複加入視為更新，不新增重複資料）。

        部分更新是刻意設計（ADR-05）：一鍵加入追蹤（WatchlistStarButton 等入口）通常不會帶
        target_price／note，若整欄覆寫會把使用者原本設好的目標價、追蹤原因清空。呼叫端只要
        把「有意義要更新」的欄位放進 data 即可，其餘欄位不傳、不覆寫。"""
        existing = await self._get_watchlist_row(data["market"], data["symbol"])
        if existing:
            for key in ("target_price", "note", "is_crawl_enabled", "source"):
                if key in data:
                    setattr(existing, key, data[key])
            if data.get("name"):
                existing.name = data["name"]
            await self._s.flush()
            tags = await self._load_tags_for([existing.id])
            return _watchlist_to_dict(existing, tags.get(existing.id)), False
        row = PortfolioWatchlist(**{k: v for k, v in data.items() if k != "tags"})
        self._s.add(row)
        await self._s.flush()
        return _watchlist_to_dict(row, []), True

    async def update_watchlist(self, watch_id: int, data: dict) -> Optional[dict]:
        """部分更新；data 只放實際要改的欄位（同 upsert_watchlist 的 ADR-05 語意）。"""
        row = await self._s.get(PortfolioWatchlist, watch_id)
        if not row:
            return None
        for k, v in data.items():
            setattr(row, k, v)
        await self._s.flush()
        tags = await self._load_tags_for([row.id])
        return _watchlist_to_dict(row, tags.get(row.id))

    async def delete_watchlist(self, watch_id: int) -> bool:
        """移除清單項目（連帶 tag 關聯，靠 DB 的 ON DELETE CASCADE）。
        不動任何已抓到的歷史價格資料（daily_stock_data / data/{tw,us}/<symbol>.json）。"""
        row = await self._s.get(PortfolioWatchlist, watch_id)
        if not row:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    async def list_crawl_enabled_symbols(self, market: str) -> list[str]:
        """供 .env 鏡像使用：is_crawl_enabled=TRUE 的代號清單（見 services/tracking_service.py）。"""
        stmt = (
            select(PortfolioWatchlist.symbol)
            .where(PortfolioWatchlist.market == market, PortfolioWatchlist.is_crawl_enabled.is_(True))
            .order_by(PortfolioWatchlist.symbol)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def set_watchlist_tags(self, watch_id: int, tag_ids: list[int]) -> None:
        """整批覆寫一個清單項目的 tag（先清空再重建，呼叫端已解析好完整 tag_id 清單）。"""
        await self._s.execute(delete(WatchlistItemTag).where(WatchlistItemTag.watchlist_id == watch_id))
        for tag_id in tag_ids:
            self._s.add(WatchlistItemTag(watchlist_id=watch_id, tag_id=tag_id))
        await self._s.flush()

    # ── 自訂標籤字典（watchlist_tag，V12） ──────────────────────────────
    async def list_tags(self) -> list[dict]:
        stmt = (
            select(WatchlistTag, func.count(WatchlistItemTag.watchlist_id))
            .outerjoin(WatchlistItemTag, WatchlistItemTag.tag_id == WatchlistTag.id)
            .group_by(WatchlistTag.id)
            .order_by(WatchlistTag.sort_order, WatchlistTag.name)
        )
        result = await self._s.execute(stmt)
        return [_tag_to_dict(tag, usage_count) for tag, usage_count in result.all()]

    async def get_tag_by_name(self, name: str) -> Optional[WatchlistTag]:
        stmt = select(WatchlistTag).where(func.lower(WatchlistTag.name) == name.strip().lower())
        return (await self._s.execute(stmt)).scalars().first()

    async def get_or_create_tags(self, names: list[str]) -> list[WatchlistTag]:
        """依名稱找既有 tag（大小寫不分），不存在則自動建立（ADR-04：LOWER(name) 去重）。"""
        tags: list[WatchlistTag] = []
        seen_ids: set[int] = set()
        for raw_name in names:
            name = (raw_name or "").strip()
            if not name:
                continue
            tag = await self.get_tag_by_name(name)
            if not tag:
                tag = WatchlistTag(name=name)
                self._s.add(tag)
                await self._s.flush()
            if tag.id not in seen_ids:
                tags.append(tag)
                seen_ids.add(tag.id)
        return tags

    async def create_tag(self, name: str, color: str = "slate") -> dict:
        if await self.get_tag_by_name(name):
            raise ValueError(f"標籤「{name}」已存在")
        tag = WatchlistTag(name=name.strip(), color=color)
        self._s.add(tag)
        await self._s.flush()
        return _tag_to_dict(tag, usage_count=0)

    async def update_tag(self, tag_id: int, patch: dict) -> Optional[dict]:
        tag = await self._s.get(WatchlistTag, tag_id)
        if not tag:
            return None
        if "name" in patch and patch["name"]:
            dup = await self.get_tag_by_name(patch["name"])
            if dup and dup.id != tag_id:
                raise ValueError(f"標籤「{patch['name']}」已存在")
        for k, v in patch.items():
            setattr(tag, k, v)
        await self._s.flush()
        return _tag_to_dict(tag)

    async def delete_tag(self, tag_id: int) -> bool:
        tag = await self._s.get(WatchlistTag, tag_id)
        if not tag:
            return False
        await self._s.delete(tag)
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
