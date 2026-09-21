"""投資筆記 AI 解析 API（docs/01_Requirements/16.AI技術分析/Phase6-投資筆記 AI 解析.md）。

掛 require_owner（比照 investment_notes.py／ai_batch.py）：筆記是私人內容，且會實際花錢呼叫 LLM。

獨立前綴 /api/v1/note-ai，而非掛在 /api/v1/investment-notes/ 底下：後者已有 GET /{note_id}，
字面路徑（如 /ai/status）會被它以 422 攔走，得靠路由註冊順序閃避，太脆弱。

只回傳「提案」，**不寫入筆記**：使用者在前端逐項勾選後，套用走既有 PATCH /investment-notes/{id}。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai import config as ai_config
from core.owner_auth import require_owner
from note_ai import analyzer
from services import investment_note_service

router = APIRouter(
    prefix="/api/v1/note-ai",
    tags=["Portfolio - Investment Notes AI"],
    dependencies=[Depends(require_owner)],
)

DISCLAIMER = "以上為 AI 依筆記內容整理的建議，圖片辨識的數字與個股代號可能有誤，請逐項確認後再套用；不構成投資建議。"


class AnalyzeRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None  # 未帶時退回該 provider 的 .env 預設模型


@router.get("/status", summary="AI 解析目前是否可用、今日用量與預設模型（解析前顯示費用提示用）")
async def get_status():
    provider = ai_config.get_default_provider()
    return {
        "success": True,
        "data": {
            "enabled": ai_config.is_enabled() and ai_config.get_note_ai_enabled(),
            "daily_quota": ai_config.get_note_ai_daily_quota(),
            "used_today": await analyzer.get_used_today(),
            "max_images": ai_config.get_note_ai_max_images(),
            "default_provider": provider,
            "default_model": analyzer.resolve_model(provider, None),
        },
    }


@router.post("/notes/{note_id}/analyze", summary="對一篇筆記做 AI 解析，回傳提案（不寫入筆記）")
async def analyze_note(note_id: int, req: AnalyzeRequest):
    note = await investment_note_service.get_note(note_id)
    if note is None:
        raise HTTPException(404, "找不到筆記")
    proposal = await analyzer.analyze_note(note, provider_code=req.provider, model=req.model)
    return {"success": True, "data": proposal, "disclaimer": DISCLAIMER}
