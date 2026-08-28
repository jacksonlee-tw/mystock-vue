"""投資筆記 REST API（設計文件 §5：docs/8.個人投資記帳功能/個人投資筆記.md）。

薄 Controller 層：欄位驗證交給 Pydantic + services/investment_note_service.py（R5：後端強制驗證），
這裡只做 HTTP 轉譯，不直接碰 InvestmentNoteRepository。狀態碼與回傳格式比照本模組其餘端點
（transactions.py／watchlist.py）既有慣例：新增／刪除一律 200 + {success, data?, message}，不採
設計文件草案中的 201/204（避免這個子模組跟系統其他 CRUD 端點的回傳慣例不一致）。
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services import investment_note_service

router = APIRouter(prefix="/api/v1/investment-notes", tags=["Portfolio - Investment Notes"])


class NoteCreate(BaseModel):
    note_date: Optional[date] = None
    subject: str
    content: str
    market: Optional[str] = None
    symbol: Optional[str] = None
    status: str = "published"
    tag_names: Optional[List[str]] = None


class NoteUpdate(BaseModel):
    note_date: Optional[date] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    market: Optional[str] = None
    symbol: Optional[str] = None
    status: Optional[str] = None
    tag_names: Optional[List[str]] = None


def _note_out(n: dict) -> dict:
    out = dict(n)
    for key in ("note_date", "created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


@router.get("", summary="分頁列表（預設 status=published，依日期降冪、同日流水號降冪排序）")
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    q: Optional[str] = Query(None, max_length=100, description="搜尋 subject 與 content"),
    tag: Optional[str] = Query(None, description="依標籤名稱篩選"),
    market: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query("published", description="published／draft／archived；'all' 代表不篩選"),
):
    if status == "all":
        status = None
    if status is not None and status not in investment_note_service.VALID_STATUSES:
        raise HTTPException(400, "status 必須為 published、draft、archived 或 all")
    if market is not None and market not in investment_note_service.VALID_MARKETS:
        raise HTTPException(400, "market 必須為 tw 或 us")

    items, total = await investment_note_service.list_notes(
        page=page, page_size=page_size, date_from=date_from, date_to=date_to,
        q=q, tag=tag, market=market, symbol=symbol.strip().upper() if symbol else None, status=status,
    )
    return {
        "success": True,
        "data": {"items": [_note_out(i) for i in items], "total": total, "page": page, "page_size": page_size},
    }


@router.get("/tags", summary="取得所有自訂標籤（含引用次數）")
async def list_tags():
    return {"success": True, "data": await investment_note_service.list_tags()}


@router.get("/{note_id}", summary="取得單筆完整內容")
async def get_note(note_id: int):
    note = await investment_note_service.get_note(note_id)
    if note is None:
        raise HTTPException(404, "找不到筆記")
    return {"success": True, "data": _note_out(note)}


@router.post("", summary="新增並配置同日下一個流水號")
async def create_note(payload: NoteCreate):
    try:
        note = await investment_note_service.create_note(payload.model_dump(exclude_unset=True))
    except investment_note_service.NoteSequenceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "success": True, "data": _note_out(note),
        "message": f"筆記已儲存 · {note['note_date'].isoformat()} #{note['sequence_no']}",
    }


@router.patch("/{note_id}", summary="部分更新欄位與標籤")
async def update_note(note_id: int, payload: NoteUpdate):
    try:
        note = await investment_note_service.update_note(note_id, payload.model_dump(exclude_unset=True))
    except investment_note_service.NoteSequenceConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if note is None:
        raise HTTPException(404, "找不到筆記")
    return {"success": True, "data": _note_out(note), "message": "筆記已更新"}


@router.delete("/{note_id}", summary="刪除筆記與標籤關聯（不影響交易或持倉）")
async def delete_note(note_id: int):
    ok = await investment_note_service.delete_note(note_id)
    if not ok:
        raise HTTPException(404, "找不到筆記")
    return {"success": True, "message": "筆記已刪除"}
