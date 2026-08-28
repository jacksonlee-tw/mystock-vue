"""投資筆記業務邏輯（見 docs/8.個人投資記帳功能/個人投資筆記.md）。

比照 services/tracking_service.py 的風格：函式各自用 get_async_session() 開一個 request 範圍外的
session、自行 commit，API 層（api/v1/endpoints/investment_notes.py）只呼叫這裡，不直接操作
InvestmentNoteRepository。流水號配置（R1／R2）與股票名稱快照都在這裡處理，讓 Repository 保持單純
的 SQL 存取層。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from db.session import get_async_session
from repositories.investment_note_repository import InvestmentNoteRepository

logger = logging.getLogger("mystock-backend")

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
MAX_TAGS = 10
MAX_SUBJECT_LEN = 200
VALID_STATUSES = ("published", "draft", "archived")
VALID_MARKETS = ("tw", "us")
_SEQUENCE_RETRY_ATTEMPTS = 2  # R2：先查後寫 + unique constraint 最終保護，衝突時重查一次


class NoteSequenceConflictError(Exception):
    """併發配置 (note_date, sequence_no) 衝突，重試後仍失敗（API 層轉 409 NOTE_SEQUENCE_CONFLICT）。"""


def today_taipei() -> date:
    return datetime.now(TAIPEI_TZ).date()


def _normalize_tag_names(names: Optional[list[str]]) -> list[str]:
    """去空白、大小寫不分去重（沿用先出現者的大小寫），最多 10 個（設計文件 §5.2）。"""
    if not names:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = (raw or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(name)
        if len(out) >= MAX_TAGS:
            break
    return out


async def _resolve_symbol_name(market: str, symbol: str) -> Optional[str]:
    """best-effort 查 symbols 主檔取得名稱快照；查詢失敗或查無資料都不阻斷筆記保存（設計文件
    §10.1：股票關聯採邏輯驗證、不建 FK，退市標的仍可保留歷史筆記），呼叫端在查無結果時退回用
    symbol 本身當作名稱快照。"""
    try:
        from repositories.stock_repository import StockRepository

        rows = await StockRepository().get_symbols([symbol], market)
        return rows[0]["name"] if rows and rows[0].get("name") else None
    except Exception as exc:
        logger.warning("[投資筆記] 查詢股票名稱快照失敗（market=%s, symbol=%s）：%s", market, symbol, exc)
        return None


def _validate_shape(subject: str, content: str, market: Optional[str], symbol: Optional[str], status: str) -> None:
    if not subject.strip():
        raise ValueError("主旨不可為空白")
    if len(subject) > MAX_SUBJECT_LEN:
        raise ValueError(f"主旨長度不可超過 {MAX_SUBJECT_LEN} 字")
    if not content.strip():
        raise ValueError("內容不可為空白")
    if bool(market) != bool(symbol):
        raise ValueError("market 與 symbol 必須同時提供或同時留空")
    if market and market not in VALID_MARKETS:
        raise ValueError("market 必須為 tw 或 us")
    if status not in VALID_STATUSES:
        raise ValueError(f"status 必須為 {'、'.join(VALID_STATUSES)} 其中之一")


async def _prepare_row(payload: dict, *, existing_symbol: Optional[str] = None) -> dict:
    """整理成可直接寫入 ORM 的欄位字典；`payload` 只放實際要寫入的欄位（新增時已補齊預設值，
    更新時由呼叫端只放有變動的欄位）。"""
    subject = payload["subject"].strip()
    content = payload["content"].strip()
    market = payload.get("market")
    symbol = payload.get("symbol").strip().upper() if payload.get("symbol") else None
    status = payload.get("status", "published")
    _validate_shape(subject, content, market, symbol, status)

    row = {"subject": subject, "content": content, "status": status}
    if "note_date" in payload:
        row["note_date"] = payload["note_date"]
    if market:
        row["market"] = market
        row["symbol"] = symbol
        # 代號沒變就不必重查一次名稱（例如只改內容/標籤的 PATCH）
        if symbol != existing_symbol:
            row["symbol_name"] = await _resolve_symbol_name(market, symbol) or symbol
    elif "market" in payload:  # 明確傳入 market=None／symbol=None，代表要清空關聯
        row["market"] = None
        row["symbol"] = None
        row["symbol_name"] = None
    return row


# ── 筆記 CRUD ────────────────────────────────────────────────────────────
async def list_notes(
    *, page: int = 1, page_size: int = 20, date_from: Optional[date] = None, date_to: Optional[date] = None,
    q: Optional[str] = None, tag: Optional[str] = None, market: Optional[str] = None,
    symbol: Optional[str] = None, status: Optional[str] = "published",
) -> tuple[list[dict], int]:
    async with get_async_session() as session:
        return await InvestmentNoteRepository(session).list_notes(
            page=page, page_size=page_size, date_from=date_from, date_to=date_to,
            q=q, tag=tag, market=market, symbol=symbol, status=status,
        )


async def get_note(note_id: int) -> Optional[dict]:
    async with get_async_session() as session:
        return await InvestmentNoteRepository(session).get_note(note_id)


async def create_note(payload: dict) -> dict:
    """新增筆記：note_date 未提供時預設台北時區今日；sequence_no 由這裡配置並在唯一鍵衝突時
    重試一次（R1／R2）。`payload` 可含 `tag_names`（list[str]，選填）。"""
    data = dict(payload)
    tag_names = _normalize_tag_names(data.pop("tag_names", None))
    note_date = data.get("note_date") or today_taipei()
    data["note_date"] = note_date

    last_error: Optional[Exception] = None
    for attempt in range(_SEQUENCE_RETRY_ATTEMPTS):
        try:
            async with get_async_session() as session:
                repo = InvestmentNoteRepository(session)
                row = await _prepare_row(data)
                row["note_date"] = note_date
                row["sequence_no"] = await repo.next_sequence_no(note_date)
                note = await repo.create_note(row)
                if tag_names:
                    tags = await repo.get_or_create_tags(tag_names)
                    await repo.set_note_tags(note["id"], [t.id for t in tags])
                    note = await repo.get_note(note["id"])
                await session.commit()
                return note
        except IntegrityError as exc:
            last_error = exc
            logger.warning("[投資筆記] 流水號配置衝突（note_date=%s），重試中：%s", note_date, exc)
            continue
    raise NoteSequenceConflictError(f"{note_date} 流水號配置衝突，請重新送出") from last_error


async def update_note(note_id: int, patch: dict) -> Optional[dict]:
    """部分更新；日期變更時視為移動到新日期並重新配置新日期流水號（設計文件 §10.1-4），一樣有
    重試保護。`patch` 可含 `tag_names`（帶入則整批覆寫，不帶則不動既有 tag）。"""
    data = dict(patch)
    tag_names_provided = "tag_names" in data
    tag_names = _normalize_tag_names(data.pop("tag_names", None)) if tag_names_provided else None

    async with get_async_session() as session:
        existing = await InvestmentNoteRepository(session).get_note(note_id)
    if not existing:
        return None

    date_changed = "note_date" in data and data["note_date"] != existing["note_date"]
    merged = {**existing, **data}
    row = await _prepare_row(merged, existing_symbol=existing.get("symbol"))
    if not date_changed:
        row.pop("note_date", None)

    last_error: Optional[Exception] = None
    for attempt in range(_SEQUENCE_RETRY_ATTEMPTS):
        try:
            async with get_async_session() as session:
                repo = InvestmentNoteRepository(session)
                write = dict(row)
                if date_changed:
                    write["sequence_no"] = await repo.next_sequence_no(merged["note_date"])
                note = await repo.update_note(note_id, write)
                if note is None:
                    return None
                if tag_names_provided:
                    tags = await repo.get_or_create_tags(tag_names)
                    await repo.set_note_tags(note_id, [t.id for t in tags])
                    note = await repo.get_note(note_id)
                await session.commit()
                return note
        except IntegrityError as exc:
            if not date_changed:
                raise
            last_error = exc
            logger.warning("[投資筆記] 更新流水號配置衝突（note_id=%s），重試中：%s", note_id, exc)
            continue
    raise NoteSequenceConflictError(f"{merged['note_date']} 流水號配置衝突，請重新送出") from last_error


async def delete_note(note_id: int) -> bool:
    async with get_async_session() as session:
        repo = InvestmentNoteRepository(session)
        ok = await repo.delete_note(note_id)
        if ok:
            await session.commit()
        return ok


# ── 自訂標籤（唯讀，標籤本身由筆記新增／編輯時自動建立） ───────────────────
async def list_tags() -> list[dict]:
    async with get_async_session() as session:
        return await InvestmentNoteRepository(session).list_tags()
