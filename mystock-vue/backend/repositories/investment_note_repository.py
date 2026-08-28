"""投資筆記模組（investment_note_* 三張表）唯一資料存取入口，API 層不得直接操作 session。

比照 repositories/portfolio_repository.py 的風格：建構子注入 AsyncSession，查詢用型別化 ORM
select()；tag 走 investment_note_tag / investment_note_tag_link，不與 watchlist_tag 共用（不同
領域各自的標籤字典，見設計文件 §3.2）。呼叫端（services/investment_note_service.py）負責
commit／rollback 與流水號衝突重試。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.note_models import InvestmentNote, InvestmentNoteTag, InvestmentNoteTagLink

EXCERPT_LENGTH = 240


def _note_to_dict(row: InvestmentNote, tags: Optional[list[dict]] = None) -> dict:
    return {
        "id": row.id, "note_date": row.note_date, "sequence_no": row.sequence_no,
        "subject": row.subject, "content": row.content,
        "market": row.market, "symbol": row.symbol, "symbol_name": row.symbol_name,
        "status": row.status, "tags": tags or [],
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _to_excerpt(note: dict) -> dict:
    """列表只回傳內容摘要，不回全文（R7）。"""
    out = dict(note)
    content = out.pop("content")
    out["content_excerpt"] = content if len(content) <= EXCERPT_LENGTH else content[:EXCERPT_LENGTH] + "…"
    return out


def _tag_to_dict(row: InvestmentNoteTag, usage_count: Optional[int] = None) -> dict:
    out = {"id": row.id, "name": row.name, "color": row.color}
    if usage_count is not None:
        out["usage_count"] = usage_count
    return out


class InvestmentNoteRepository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ── 筆記 CRUD ────────────────────────────────────────────────────
    async def _load_tags_for(self, note_ids: list[int]) -> dict[int, list[dict]]:
        """批次撈多篇筆記的 tag，避免逐筆各查一次（N+1）。"""
        if not note_ids:
            return {}
        stmt = (
            select(InvestmentNoteTagLink.note_id, InvestmentNoteTag)
            .join(InvestmentNoteTag, InvestmentNoteTag.id == InvestmentNoteTagLink.tag_id)
            .where(InvestmentNoteTagLink.note_id.in_(note_ids))
            .order_by(InvestmentNoteTag.name)
        )
        result = await self._s.execute(stmt)
        out: dict[int, list[dict]] = {}
        for note_id, tag in result.all():
            out.setdefault(note_id, []).append(_tag_to_dict(tag))
        return out

    async def next_sequence_no(self, note_date: date) -> int:
        stmt = select(func.coalesce(func.max(InvestmentNote.sequence_no), 0) + 1).where(
            InvestmentNote.note_date == note_date
        )
        return (await self._s.execute(stmt)).scalar_one()

    async def list_notes(
        self, *, page: int = 1, page_size: int = 20,
        date_from: Optional[date] = None, date_to: Optional[date] = None,
        q: Optional[str] = None, tag: Optional[str] = None,
        market: Optional[str] = None, symbol: Optional[str] = None,
        status: Optional[str] = "published",
    ) -> tuple[list[dict], int]:
        conditions = []
        if status:
            conditions.append(InvestmentNote.status == status)
        if date_from:
            conditions.append(InvestmentNote.note_date >= date_from)
        if date_to:
            conditions.append(InvestmentNote.note_date <= date_to)
        if q:
            like = f"%{q}%"
            conditions.append(or_(InvestmentNote.subject.ilike(like), InvestmentNote.content.ilike(like)))
        if market:
            conditions.append(InvestmentNote.market == market)
        if symbol:
            conditions.append(InvestmentNote.symbol == symbol)
        if tag:
            sub = (
                select(InvestmentNoteTagLink.note_id)
                .join(InvestmentNoteTag, InvestmentNoteTag.id == InvestmentNoteTagLink.tag_id)
                .where(func.lower(InvestmentNoteTag.name) == tag.strip().lower())
            )
            conditions.append(InvestmentNote.id.in_(sub))

        count_stmt = select(func.count()).select_from(InvestmentNote)
        list_stmt = select(InvestmentNote)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            list_stmt = list_stmt.where(cond)

        total = (await self._s.execute(count_stmt)).scalar_one()
        list_stmt = (
            list_stmt.order_by(InvestmentNote.note_date.desc(), InvestmentNote.sequence_no.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._s.execute(list_stmt)).scalars().all()
        tags_by_note = await self._load_tags_for([r.id for r in rows])
        items = [_to_excerpt(_note_to_dict(r, tags_by_note.get(r.id))) for r in rows]
        return items, total

    async def get_note(self, note_id: int) -> Optional[dict]:
        row = await self._s.get(InvestmentNote, note_id)
        if not row:
            return None
        tags = await self._load_tags_for([row.id])
        return _note_to_dict(row, tags.get(row.id))

    async def create_note(self, data: dict) -> dict:
        row = InvestmentNote(**data)
        self._s.add(row)
        await self._s.flush()
        return _note_to_dict(row, [])

    async def update_note(self, note_id: int, data: dict) -> Optional[dict]:
        row = await self._s.get(InvestmentNote, note_id)
        if not row:
            return None
        for k, v in data.items():
            setattr(row, k, v)
        row.updated_at = datetime.now(timezone.utc)
        await self._s.flush()
        tags = await self._load_tags_for([row.id])
        return _note_to_dict(row, tags.get(row.id))

    async def delete_note(self, note_id: int) -> bool:
        row = await self._s.get(InvestmentNote, note_id)
        if not row:
            return False
        await self._s.delete(row)
        await self._s.flush()
        return True

    async def set_note_tags(self, note_id: int, tag_ids: list[int]) -> None:
        """整批覆寫一篇筆記的 tag（先清空再重建）。"""
        from sqlalchemy import delete

        await self._s.execute(delete(InvestmentNoteTagLink).where(InvestmentNoteTagLink.note_id == note_id))
        for tag_id in tag_ids:
            self._s.add(InvestmentNoteTagLink(note_id=note_id, tag_id=tag_id))
        await self._s.flush()

    # ── 自訂標籤字典（investment_note_tag） ─────────────────────────
    async def list_tags(self) -> list[dict]:
        stmt = (
            select(InvestmentNoteTag, func.count(InvestmentNoteTagLink.note_id))
            .outerjoin(InvestmentNoteTagLink, InvestmentNoteTagLink.tag_id == InvestmentNoteTag.id)
            .group_by(InvestmentNoteTag.id)
            .order_by(InvestmentNoteTag.name)
        )
        result = await self._s.execute(stmt)
        return [_tag_to_dict(tag, usage_count) for tag, usage_count in result.all()]

    async def get_tag_by_name(self, name: str) -> Optional[InvestmentNoteTag]:
        stmt = select(InvestmentNoteTag).where(func.lower(InvestmentNoteTag.name) == name.strip().lower())
        return (await self._s.execute(stmt)).scalars().first()

    async def get_or_create_tags(self, names: list[str]) -> list[InvestmentNoteTag]:
        """依名稱找既有 tag（大小寫不分），不存在則自動建立；呼叫端已負責去重與上限 10 個。"""
        tags: list[InvestmentNoteTag] = []
        seen_ids: set[int] = set()
        for raw_name in names:
            name = (raw_name or "").strip()
            if not name:
                continue
            tag = await self.get_tag_by_name(name)
            if not tag:
                tag = InvestmentNoteTag(name=name)
                self._s.add(tag)
                await self._s.flush()
            if tag.id not in seen_ids:
                tags.append(tag)
                seen_ids.add(tag.id)
        return tags
