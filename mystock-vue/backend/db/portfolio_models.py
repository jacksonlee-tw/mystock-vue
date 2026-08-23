"""個人投資記帳與績效追蹤模組 SQLAlchemy 2.0 ORM 模型（對應 V8__Create_portfolio_ledger.sql）。

沿用 db/models.py 的 typed Mapped/mapped_column 風格（這個新領域不像 db/notify_models.py 需要相容舊
Column() 慣例）。見 docs/8.個人投資記帳功能/個人投資記帳功能_design.md。
"""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    TIMESTAMP,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


class PortfolioTransaction(Base):
    """買賣交易明細（設計文件 §一）。fee/tax 於寫入當下算好凍結，見 services/portfolio_ledger.py。"""
    __tablename__ = "portfolio_transaction"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy | sell
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    trade_time: Mapped[Optional[time]] = mapped_column(Time)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    odd_lot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    fee_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class PortfolioDividend(Base):
    """現金／股票股利領取紀錄（設計文件 §四）。"""
    __tablename__ = "portfolio_dividend"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # cash | stock
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    shares: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class PortfolioCashflow(Base):
    """本金出入金紀錄（設計文件 §四）。"""
    __tablename__ = "portfolio_cashflow"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # deposit | withdraw
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class PortfolioWatchlist(Base):
    """個股追蹤與觀察清單（原「潛力股觀察名單」，設計文件 §五；整合擴充見
    docs/14.追蹤個股清單優化/追蹤與觀察名單整合_規劃書.md §4）。同 (market, symbol) 唯一，
    見 V8 的 uq_portfolio_watchlist_market_symbol。target_price 為 NULL 代表「純追蹤」（V12）：
    只納入每日抓取範圍、不計算距目標／到價提醒。tags 由 repository 另外查詢組裝，不用
    relationship()：async session 下 lazy-load 會觸發 MissingGreenlet。"""
    __tablename__ = "portfolio_watchlist"
    __table_args__ = (UniqueConstraint("market", "symbol", name="uq_portfolio_watchlist_market_symbol"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    added_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    target_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_crawl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class WatchlistTag(Base):
    """追蹤與觀察名單的自訂標籤字典（跨市場共用，V12）。名稱唯一以 LOWER(name) 索引控管
    （見 migration），ORM 層不重複宣告，由 repository 的 upsert 邏輯負責去重。"""
    __tablename__ = "watchlist_tag"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="slate")
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class WatchlistItemTag(Base):
    """清單項目 <-> tag 多對多關聯（V12）。純關聯表，兩側皆 ON DELETE CASCADE。"""
    __tablename__ = "watchlist_item_tag"

    watchlist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("portfolio_watchlist.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("watchlist_tag.id", ondelete="CASCADE"), primary_key=True
    )


class PortfolioSettings(Base):
    """記帳試算參數，單一列（id=1），見 GET/PUT /api/v1/settings。"""
    __tablename__ = "portfolio_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    tw_fee_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0.001425"))
    tw_fee_discount: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("0.6"))
    tw_fee_min: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("20"))
    tw_tax_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0.003"))
    tw_tax_rate_etf: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0.001"))
    us_fee_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))
    us_sec_fee_rate: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=Decimal("0.0000278"))
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("32.5"))
    cost_method: Mapped[str] = mapped_column(String(10), nullable=False, default="fifo")
    dividend_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="income")
    near_target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("3"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
