"""黃金價格查詢 API 路由（Controller 層）

代理上游 TPEX OpenAPI，避免前端跨域存取問題。
資料來源：證券櫃檯買賣中心 https://www.tpex.org.tw/openapi/
"""
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/gold", tags=["黃金價格"])

_TPEX_GOLD_URL = "https://www.tpex.org.tw/openapi/v1/tpex_gold_latest"
_HEADERS = {
    "accept": "application/json",
    "If-Modified-Since": "Mon, 26 Jul 1997 05:00:00 GMT",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


@router.get("/latest", summary="取得最新黃金價格")
async def get_gold_latest():
    """取得最新黃金現貨價格。

    代理轉送至證券櫃檯買賣中心 OpenAPI（tpex_gold_latest），
    直接回傳原始 JSON 陣列，欄位依 TPEX 當日實際回傳為準。

    Returns:
        list[dict]: 黃金價格清單（買進價、賣出價等）
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_TPEX_GOLD_URL, headers=_HEADERS)
            resp.raise_for_status()
            return {"status": "ok", "data": resp.json()}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TPEX API 請求逾時，請稍後再試")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"TPEX API 回傳錯誤：HTTP {e.response.status_code}",
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"TPEX API 連線失敗：{e}")
