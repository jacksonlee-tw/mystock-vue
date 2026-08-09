"""入廠過磅業務邏輯層（UC-001）

負責入廠過磅確認的核心商業邏輯。
透過 UnitOfWork 存取 Repository，並統一控制交易邊界。
"""
import logging
from datetime import datetime

from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.domain.entities.weigh_ticket import WeighTicket
from backend.domain.ports.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


def confirm_entry(uow: UnitOfWork, record, locale: str = DEFAULT_LOCALE) -> dict:
    """UC-001：入廠過磅確認（業務邏輯）。

    車號、採購單號為必填（Pydantic 於 Router 層已驗證）。
    依 scaleType 對應 workFlow（1/2/3），產生 10 碼磅單號並 INSERT CMM_SCALE。
    成功訊息透過 translate() 依語系回傳，不寫死任何語言文字。
    """
    now = datetime.now()
    dbno = uow.tickets.next_dbno()

    arr_d = record.entryDate.strftime("%Y%m%d") if record.entryDate else now.strftime("%Y%m%d")
    arr_t = record.entryTime.strftime("%H%M%S") if record.entryTime else now.strftime("%H%M%S")

    # Domain Entity：工作流程對應規則
    workflow = WeighTicket.resolve_workflow(str(record.scaleType or "double"))
    weigth1 = int(record.entryWeightA1 or 0)
    snet    = int(record.netWeightSupplier or 0) or None
    nnet    = int(record.netWeightNotary or 0) or None

    row = {
        "truckNo":  str(record.carNo or "").strip(),
        "poNo":     str(record.poNo or "").strip(),
        "prodName": str(record.materialName or "").strip(),
        "supply":   str(record.supplier or "").strip(),
        "sNet":     snet,
        "nNet":     nnet,
        "weigth1":  weigth1,
        "arrDate":  arr_d,
        "arrTime":  arr_t,
        "workFlow": workflow,
        "batchNo":  str(record.batchNo or "").strip(),
        "boatNo":   str(record.shipNo or "").strip(),
        "trancomp": str(record.carrier or "").strip(),
        "printCount": 0,
        "entryAt":  now.isoformat(),
    }

    uow.tickets.create_entry(dbno, row)
    uow.commit()

    log.info("[入廠確認] 磅單=%s 車號=%s 採購單=%s A1=%s Kg",
             dbno, record.carNo, record.poNo, record.entryWeightA1)

    return {
        "status":    "success",
        "message":   translate("ENTRY_CONFIRM_SUCCESS", locale, car_no=record.carNo),
        "ticketNo":  dbno,
        "timestamp": now.isoformat(),
        "dbMode":    uow.db_mode,
    }
