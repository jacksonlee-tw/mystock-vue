"""投資筆記模組 SQLAlchemy 2.0 ORM 模型（對應 V16__Create_investment_notes.sql）。

見 docs/8.個人投資記帳功能/個人投資筆記.md。沿用 db/portfolio_models.py 的 typed Mapped/mapped_column
風格與 WatchlistTag/WatchlistItemTag 的多對多 tag 慣例（不用 relationship()：async session 下
lazy-load 會觸發 MissingGreenlet，tag 一律由 repository 另外批次查詢組裝）。
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.models import Base


class InvestmentNote(Base):
    """投資筆記主表（設計文件 §3.1）。同一 note_date 的 sequence_no 從 1 起算，刪除筆記後不重排既有
    流水號（R1）；(note_date, sequence_no) 由 DB unique constraint 做最終併發保護（R2），配置邏輯見
    services/investment_note_service.py。"""
    __tablename__ = "investment_note"
    __table_args__ = (UniqueConstraint("note_date", "sequence_no", name="uq_investment_note_date_sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    note_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[Optional[str]] = mapped_column(String(10))
    symbol: Mapped[Optional[str]] = mapped_column(String(20))
    symbol_name: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="published")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class InvestmentNoteTag(Base):
    """投資筆記自訂標籤字典（設計文件 §3.2）。名稱去空白、不分大小寫唯一，由 migration 的
    LOWER(name) 唯一索引控管，ORM 層不重複宣告，由 repository 的 get_or_create_tags() 負責去重。"""
    __tablename__ = "investment_note_tag"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="slate")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class InvestmentNoteTagLink(Base):
    """筆記 <-> 標籤多對多關聯（設計文件 §3.3）。純關聯表，兩側皆 ON DELETE CASCADE。"""
    __tablename__ = "investment_note_tag_link"

    note_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("investment_note.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("investment_note_tag.id", ondelete="CASCADE"), primary_key=True
    )
