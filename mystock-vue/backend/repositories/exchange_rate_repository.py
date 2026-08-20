"""每日匯率資料存取入口（見 db/exchange_rate_models.py / V11__Create_exchange_rate.sql）。

比照 repositories/portfolio_repository.py：建構子注入 AsyncSession，查詢用型別化 ORM select()；
UPSERT 比照 repositories/market_repository.py 的 pg_insert().on_conflict_do_update() 寫法。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.exchange_rate_models import ExchangeRate

CURRENCIES = ("USD", "JPY", "CNY")


def _row_to_dict(row: ExchangeRate) -> dict:
    return {
        "currency": row.currency, "rate_date": row.rate_date,
        "rate": row.rate, "source": row.source, "fetched_at": row.fetched_at,
    }


class ExchangeRateRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def upsert_many(self, rows: list[dict]) -> int:
        """rows: [{currency, rate_date, rate, source}, ...]。
        同一 (rate_date, currency) 已存在則覆蓋（見 V11 的 uq_exchange_rate_date_currency）。"""
        if not rows:
            return 0
        stmt = pg_insert(ExchangeRate).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["rate_date", "currency"],
            set_={"rate": stmt.excluded.rate, "source": stmt.excluded.source, "fetched_at": func.now()},
        )
        res = await self._s.execute(stmt)
        return res.rowcount

    async def get_latest(self) -> dict[str, dict]:
        """USD/JPY/CNY 各自最新一筆，供「股票與爬蟲管理」頁的匯率卡片顯示。"""
        out: dict[str, dict] = {}
        for currency in CURRENCIES:
            stmt = (
                select(ExchangeRate)
                .where(ExchangeRate.currency == currency)
                .order_by(ExchangeRate.rate_date.desc())
                .limit(1)
            )
            row = (await self._s.execute(stmt)).scalars().first()
            if row:
                out[currency] = _row_to_dict(row)
        return out

    async def get_rate_for_date(self, currency: str, on_date: date) -> Optional[Decimal]:
        """回傳 on_date 當天或最近一個更早的營業日的匯率（週末/假日沒有更新時往前找）。
        找不到任何資料回傳 None，呼叫端（transactions.py）以「—」顯示，不用手動 fx_rate 頂替
        （見 docs/8.個人投資記帳功能/個人投資記帳功能_design.md 補充章節的範圍邊界說明）。"""
        stmt = (
            select(ExchangeRate.rate)
            .where(ExchangeRate.currency == currency, ExchangeRate.rate_date <= on_date)
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalars().first()

    async def get_rates_for_dates(self, currency: str, dates: set[date]) -> dict[date, Decimal]:
        """list_transactions() 批次查詢用：對每個唯一交易日各查一次最近可用匯率（個人記帳用量小，
        不需要一次性 SQL batch，見設計文件）。"""
        out: dict[date, Decimal] = {}
        for d in dates:
            rate = await self.get_rate_for_date(currency, d)
            if rate is not None:
                out[d] = rate
        return out
