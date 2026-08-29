"""SQLAlchemy 2.0 ORM 模型，對應設計文件第 3.1 節與 database_design_erd_uml.md 的 ERD/UML。"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Symbol(Base):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    exchange: Mapped[Optional[str]] = mapped_column(String(20))
    security_type: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class DailyStockData(Base):
    __tablename__ = "daily_stock_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("symbols.symbol"), nullable=False)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    high_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    low_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    close_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    turnover: Mapped[Optional[int]] = mapped_column(BigInteger)
    transaction_count: Mapped[Optional[int]] = mapped_column(Integer)
    market_specific_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class CrawlerLog(Base):
    __tablename__ = "crawler_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    symbols_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    symbols_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class MarketNoTradingDay(Base):
    __tablename__ = "market_no_trading_days"

    market_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="probed")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class SymbolIndustry(Base):
    __tablename__ = "symbol_industry"

    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("symbols.symbol"), primary_key=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False)
    industry_code: Mapped[str] = mapped_column(String(50), nullable=False)
    industry_name: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class DailyMarketQuote(Base):
    __tablename__ = "daily_market_quote"

    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("symbols.symbol"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="tw")
    exchange: Mapped[Optional[str]] = mapped_column(String(20))
    open_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    high_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    low_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    close_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    change_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    change_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    turnover: Mapped[Optional[int]] = mapped_column(BigInteger)
    transaction_count: Mapped[Optional[int]] = mapped_column(Integer)
    data_quality: Mapped[str] = mapped_column(String(10), nullable=False, default="ok")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="MI_INDEX")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class DailyMarketChip(Base):
    __tablename__ = "daily_market_chip"

    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("symbols.symbol"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="tw")
    exchange: Mapped[Optional[str]] = mapped_column(String(20))
    foreign_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    trust_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    dealer_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    institutional_net: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_balance: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_buy: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_sell: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_redeem: Mapped[Optional[int]] = mapped_column(BigInteger)
    margin_quota: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_balance: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_buy: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_sell: Mapped[Optional[int]] = mapped_column(BigInteger)
    short_redeem: Mapped[Optional[int]] = mapped_column(BigInteger)
    offset_amount: Mapped[Optional[int]] = mapped_column(BigInteger)
    data_quality: Mapped[str] = mapped_column(String(10), nullable=False, default="ok")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="T86+MI_MARGN")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class DailyValuation(Base):
    __tablename__ = "daily_valuation"

    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("symbols.symbol"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="tw")
    exchange: Mapped[Optional[str]] = mapped_column(String(20))
    pe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    pb_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    dividend_yield: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    market_cap: Mapped[Optional[int]] = mapped_column(BigInteger)
    mcap_rank: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="BWIBBU")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class MonthlyRevenue(Base):
    __tablename__ = "monthly_revenue"

    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("symbols.symbol"), primary_key=True)
    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    market_type: Mapped[str] = mapped_column(String(10), nullable=False, default="tw")
    revenue: Mapped[Optional[int]] = mapped_column(BigInteger)
    mom_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    yoy_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    announced_date: Mapped[Optional[date]] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="TWSE_OPENAPI")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())


class MarketFetchJob(Base):
    __tablename__ = "market_fetch_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    targets: Mapped[str] = mapped_column(String(100), nullable=False, default="quote,chip,valuation")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    cursor_date: Mapped[Optional[date]] = mapped_column(Date)
    total_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="schedule")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
