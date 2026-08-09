"""過磅相關 Pydantic 回應模型 (Response DTOs)

提供 FastAPI Swagger 自動文件與前後端型別同步。
每個端點有對應的 Response Schema，宣告於 @router 的 response_model 參數。
"""
from typing import List, Optional

from pydantic import BaseModel


# ── 共用基底 ──────────────────────────────────────────────────────────────


class BaseResponse(BaseModel):
    """所有回應共用的基底欄位"""
    status: str


class SuccessMessageResponse(BaseResponse):
    """僅含 status + message 的通用成功回應"""
    message: str


class TelegramAlertResponse(BaseResponse):
    """POST /api/notify/telegram 回應"""
    message: str
    telegram_msg_id: Optional[int] = None


# ── 入廠 (UC-001) ────────────────────────────────────────────────────────


class EntryConfirmResponse(BaseResponse):
    """POST /api/in/confirm 回應"""
    message: str
    ticketNo: str
    timestamp: str
    dbMode: str


# ── 出廠 (UC-002) ────────────────────────────────────────────────────────


class ExitConfirmResponse(BaseResponse):
    """POST /api/out/confirm 回應"""
    message: str
    netWeight: Optional[int] = None
    timestamp: str
    dbMode: str


# ── 列印 (UC-003) ────────────────────────────────────────────────────────


class ReprintResponse(BaseResponse):
    """POST /api/print 回應"""
    message: str
    printCount: int


# ── 磅單查詢 ─────────────────────────────────────────────────────────────


class TicketDetailResponse(BaseResponse):
    """GET /api/ticket/{ticket_no} 回應"""
    ticketStatus: str = "in_progress"
    dbNo: Optional[str] = None
    truckNo: Optional[str] = None
    poNo: Optional[str] = None
    prodName: Optional[str] = None
    supplier: Optional[str] = None
    sNet: Optional[float] = None
    nNet: Optional[float] = None
    weigth1: Optional[float] = None
    weigth2: Optional[float] = None
    weigth3: Optional[float] = None
    weigth4: Optional[float] = None
    net: Optional[float] = None
    arrDate: Optional[str] = None
    arrTime: Optional[str] = None
    leftDate: Optional[str] = None
    leftTime: Optional[str] = None
    abFlag: Optional[str] = None
    batchNo: Optional[str] = None
    boatNo: Optional[str] = None
    trancomp: Optional[str] = None
    workFlow: Optional[str] = None
    printNum: Optional[int] = None
    outPrintNum: Optional[int] = None
    delFlag: Optional[bool] = None
    rTruckNo: Optional[str] = None
    rPoNo: Optional[str] = None
    rProdName: Optional[str] = None
    rSupply: Optional[str] = None


class TodayTicketItem(BaseModel):
    """當日磅單清單中的單筆項目"""
    dbNo: str
    truckNo: str = ""
    poNo: str = ""
    prodName: str = ""
    weigth1: Optional[float] = None
    weigth4: Optional[float] = None
    net: Optional[float] = None
    arrDate: str = ""
    arrTime: str = ""
    delFlag: bool = False
    status: str = "in_progress"


class TodayTicketsResponse(BaseModel):
    """GET /api/tickets/today 回應"""
    date: str
    count: int
    tickets: List[TodayTicketItem]
    dbMode: str


# ── 採購單 (UC-005) ──────────────────────────────────────────────────────


class PoInfoResponse(BaseResponse):
    """GET /api/po/{po_no} 回應"""
    poNo: str
    materialName: str = ""
    supplier: str = ""
    planQty: float = 0.0
    usedQty: float = 0.0
    ratio: float = 0.0
    closed: bool = False


# ── 超重授權 ─────────────────────────────────────────────────────────────


class OverweightAuthResponse(BaseResponse):
    """POST /api/auth/overweight 回應"""
    userNo: str
    userName: str = ""
    message: str


# ── 車輛清單 ─────────────────────────────────────────────────────────────


class TruckItem(BaseModel):
    """車輛清單中的單筆項目"""
    truckNo: str
    lastProdName: str = ""
    lastDbNo: str = ""
    trancomp: str = ""


class TruckListResponse(BaseModel):
    """GET /api/trucks 回應"""
    count: int
    trucks: List[TruckItem]


# ── 警告日誌 ─────────────────────────────────────────────────────────────
# 使用 SuccessMessageResponse


# ── 追蹤記錄 ─────────────────────────────────────────────────────────────


class TraceResponse(BaseResponse):
    """POST /api/trace 回應"""
    message: str
    traceId: Optional[str] = None


# ── DB 狀態 ──────────────────────────────────────────────────────────────


class DbStatusResponse(BaseModel):
    """GET /api/db/status 回應"""
    connected: bool
    mode: str
    server: str
    database: str
    compNo: str
    plantNo: str


# ── 讀卡機 ───────────────────────────────────────────────────────────────


class CardReadResponse(BaseResponse):
    """GET /api/device/card/read 回應"""
    message: str
    cardNo: str
