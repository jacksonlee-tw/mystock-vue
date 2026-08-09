"""過磅相關 Pydantic 資料模型 (DTOs)"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── 請求 Schemas (Request DTOs) ──────────────────────────────────────────


class EntryRecord(BaseModel):
    """入廠過磅記錄"""
    carNo: str
    shipNo: Optional[str] = ""
    poNo: str
    batchNo: Optional[str] = ""
    carrier: Optional[str] = ""
    netWeightSupplier: Optional[float] = None
    netWeightNotary: Optional[float] = None
    materialName: Optional[str] = ""
    supplier: Optional[str] = ""
    entryDate: Optional[datetime] = None
    entryTime: Optional[datetime] = None
    entryWeightA1: Optional[float] = None
    scaleType: str = "double"


class ExitRecord(BaseModel):
    """出廠過磅記錄"""
    ticketNo: str
    exitWeightB1: Optional[float] = None
    storageWeightA2: Optional[float] = None
    outboundWeightB2: Optional[float] = None
    corrCarNo: Optional[str] = ""
    corrPoNo: Optional[str] = ""
    corrBatchNo: Optional[str] = ""
    corrNetWeightSupplier: Optional[float] = None
    corrNetWeightNotary: Optional[float] = None
    corrMaterialName: Optional[str] = ""
    corrSupplierName: Optional[str] = ""
    exitDate: Optional[datetime] = None
    exitTime: Optional[datetime] = None
    exitStatus: str = "normal"
    isReturn: bool = False


class PrintRequest(BaseModel):
    """列印請求"""
    ticketNo: str
    type: str = "in"   # "in" | "out"


class OverweightAuthRequest(BaseModel):
    """超重主管覆核請求 DTO。

    當入廠重量超過系統設定上限（MMPARAS.mm_a1wgt）時，
    需由主管輸入帳號密碼進行覆核放行。
    對應 Delphi Panel2（EdtUser / EdtPwd）+ Button12Click 驗證邏輯。
    查詢資料表：user_mstr1。
    """
    userNo: str              # 主管帳號（user_mstr1.userNo）
    password: str            # 主管密碼（user_mstr1.password）
    ticketWeight: float      # 本次入廠重量（Kg），用於日誌記錄
    weightLimit: float       # 系統設定重量上限（Kg），用於日誌記錄


class WarnlogRequest(BaseModel):
    """採購量警示日誌寫入請求 DTO。

    對應 Delphi IsWarningMessage 中的 INSERT INTO Warnlog 邏輯。
    當累計進貨量達 80%/90%/100% 時，前端呼叫此端點寫入警示記錄。
    寫入資料表：Warnlog。
    """
    dbNo: str                        # 磅單號碼（CMM_SCALE.DBNo）
    aufnr: str                       # 採購單號（MM_POWO_SCALE.AUFNR）
    truckNo: Optional[str] = ""      # 車號
    planQty: Optional[int] = 0       # 採購計劃數量（MENGE，Kg）
    loadQty: Optional[int] = 0       # 本次裝載量（weigth1，Kg）
    currentQty: Optional[int] = 0    # 目前累計進貨量（InQty，Kg）
    log: Optional[str] = ""          # 警示訊息內容（例：「採購量已達 90%」）


class TelegramAlertRequest(BaseModel):
    """Telegram 股票警示訊息發送請求 DTO。

    傳送 HTML 格式訊息到設定的 Telegram Bot。
    """
    message: str                     # 訊息內容（支援 HTML 格式）
    parse_mode: str = "HTML"         # 訊息格式："HTML" 或 "Markdown"


class TraceRequest(BaseModel):
    """追蹤記錄寫入請求 DTO。

    對應 Delphi ushare.pas 中的 insertIntotrace_mstr 程序。
    每次入廠/出廠/異常操作後，寫入稽核追蹤記錄。
    寫入資料表：trace_mstr。
    """
    dbNo: str                        # 磅單號碼（trace_mstr.dbno）
    version: Optional[str] = "0"    # 磅單版本號（trace_mstr.version）
    poNo: Optional[str] = ""         # 採購單號（trace_mstr.pono）
    eventName: Optional[str] = ""   # 事件名稱（例：「入廠過磅(A1)」）
    truckNo: Optional[str] = ""      # 車號（trace_mstr.truckno）
    supply: Optional[str] = ""       # 供應商（trace_mstr.supply）
    prodName: Optional[str] = ""     # 原料名稱（trace_mstr.prodname）
    a1Wt: Optional[str] = ""         # A1 進廠重量字串（trace_mstr.A1_WT）
    a2Wt: Optional[str] = ""         # A2 入庫重量字串（trace_mstr.A2_WT）
    b2Wt: Optional[str] = ""         # B2 出庫重量字串（trace_mstr.B2_WT）
    b1Wt: Optional[str] = ""         # B1 出廠重量字串（trace_mstr.B1_WT）
    userNo: Optional[str] = ""       # 操作員帳號（trace_mstr.userno）
    workFlow: Optional[str] = ""     # 工作流程代碼（1/2/3）
