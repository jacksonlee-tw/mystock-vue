"""每日匯率資料 SQLAlchemy 2.0 ORM 模型（對應 V11__Create_exchange_rate.sql）。

沿用 db/portfolio_models.py 的 typed Mapped/mapped_column 風格。見
docs/8.個人投資記帳功能/個人投資記帳功能_design.md 補充章節。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Numeric, String, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


class ExchangeRate(Base):
    """每日市場參考匯率，每日一筆／幣別（services/exchange_rate_fetcher.py 抓取寫入）。

    來源是 fawazahmed0/currency-api（非台灣銀行牌告，見 V11 遷移檔的說明），只有單一參考匯率，
    沒有現金/即期、買入/賣出的區分，所以只有一個 rate 欄位。"""
    __tablename__ = "exchange_rate"
    __table_args__ = (UniqueConstraint("rate_date", "currency", name="uq_exchange_rate_date_currency"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # USD | JPY | CNY
    rate: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False)  # 1 單位外幣兌換多少 TWD
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="fawazahmed0-currency-api")
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
