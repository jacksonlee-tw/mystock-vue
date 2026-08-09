"""黃金價格相關 Pydantic 回應模型 (Response DTOs)

來源：證券櫃檯買賣中心 OpenAPI
https://www.tpex.org.tw/openapi/v1/tpex_gold_latest
"""
from pydantic import BaseModel, ConfigDict


class GoldPriceItem(BaseModel):
    """單筆黃金價格紀錄（直接對應 TPEX API 回傳欄位）"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # TPEX 回傳欄位（以中文為主，保留原始名稱）
    # 使用 extra="allow" 相容 TPEX API 未來欄位異動


class GoldLatestResponse(BaseModel):
    """GET /api/gold/latest 回應"""

    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    data: list[GoldPriceItem]
