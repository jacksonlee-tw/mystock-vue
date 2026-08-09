"""WebSocket 即時重量推播路由"""
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.weight_service import weight_generator

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/weight")
async def websocket_weight(websocket: WebSocket):
    """即時地磅重量推播（WebSocket）。

    客戶端連線後，每 0.5 秒推播一次模擬磅秤重量數值，
    對應 Delphi UScale.StartWeigh + COM Port 定時器讀重邏輯。
    前端 useWebSocket.js composable 透過此端點取得即時重量，
    顯示於 WeightBoard.vue 並在確認過磅時帶入重量欄位。

    推播訊息格式：
        { weight: float,  # 重量數值（Kg，模擬值 2000 ± 8）
          unit: "Kg",
          timestamp: str  # ISO 8601 時間戳 }

    斷線時自動捕捉 WebSocketDisconnect，結束生成器。
    """
    await websocket.accept()
    try:
        async for weight in weight_generator():
            await websocket.send_json({
                "weight": weight,
                "unit": "Kg",
                "timestamp": datetime.now().isoformat(),
            })
    except WebSocketDisconnect:
        print("Client disconnected from /ws/weight")
