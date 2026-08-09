"""讀卡機 API 端點（Controller 層）

提供 IC 卡讀卡功能的 REST API。
使用 Dishka DI 注入 CardReaderPort，依環境自動選擇 Mock 或真實 Driver。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute

from backend.core.i18n import get_locale
from backend.devices.base import CardReaderPort
from backend.devices.services.card_reader_service import (
    read_card_no,
    DEFAULT_PORT,
    DEFAULT_BAUD,
)
from backend.schemas.responses import CardReadResponse

router = APIRouter(prefix="/api/device", tags=["設備-讀卡機"], route_class=DishkaRoute)


@router.get("/card/read", response_model=CardReadResponse)
def api_read_card(
    reader: FromDishka[CardReaderPort],
    port: int = Query(DEFAULT_PORT, description="COM 埠號（USB 型號用 100）"),
    baud: int = Query(DEFAULT_BAUD, description="鮑率"),
    locale: str = Depends(get_locale),
):
    """讀取 IC 卡卡號（SNR）。

    開啟讀卡器 → 偵測卡片 → 讀取卡號 → 關閉讀卡器。
    無卡時回傳 404，讀卡器連線失敗回傳 500。
    """
    return read_card_no(reader, port=port, baud=baud, locale=locale)
