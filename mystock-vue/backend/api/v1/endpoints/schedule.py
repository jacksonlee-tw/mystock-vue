"""每日抓取排程設定 API。

排程時間原本寫死在 services/scheduler.py（台股 14:30、美股 06:00），改為可由 UI 設定：
設定值存在 .env（比照 config.save_target_stocks 的既有慣例），存檔後直接套用到執行中的
APScheduler，不需重啟服務。
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from config import DEFAULT_SCHEDULE_TIMES, parse_schedule_time, save_schedule_config
from services.scheduler import apply_schedule_config, get_schedule_status

router = APIRouter(prefix="/api/v1/schedule", tags=["Schedule"])


class MarketSchedulePatch(BaseModel):
    time: Optional[str] = None      # "HH:MM"（24 小時制）
    enabled: Optional[bool] = None


class ScheduleUpdateRequest(BaseModel):
    markets: dict[str, MarketSchedulePatch]


@router.get("", summary="查詢每日抓取排程設定與下次執行時間")
def get_schedule():
    return {"success": True, "data": get_schedule_status()}


@router.put("", summary="更新每日抓取排程時間（存檔後即時套用，不需重啟）")
def update_schedule(req: ScheduleUpdateRequest):
    if not req.markets:
        return {
            "success": False,
            "error": {"code": "EMPTY_PAYLOAD", "message": "請至少提供一個市場的排程設定"}
        }

    unknown = [m for m in req.markets if m not in DEFAULT_SCHEDULE_TIMES]
    if unknown:
        return {
            "success": False,
            "error": {"code": "UNSUPPORTED_MARKET", "message": f"不支援的市場：{', '.join(unknown)}"}
        }

    # 先驗證全部時間格式再寫檔，避免一半有效一半無效造成設定寫到一半
    for market, patch in req.markets.items():
        if patch.time is not None:
            try:
                parse_schedule_time(patch.time)
            except ValueError as e:
                return {
                    "success": False,
                    "error": {"code": "INVALID_TIME", "message": f"{market}：{e}"}
                }

    try:
        save_schedule_config({m: p.model_dump(exclude_none=True) for m, p in req.markets.items()})
    except (OSError, ValueError) as e:
        return {
            "success": False,
            "error": {"code": "SAVE_FAILED", "message": f"排程設定儲存失敗：{e}"}
        }

    status = apply_schedule_config()
    return {"success": True, "message": "排程已更新並即時套用", "data": status}
