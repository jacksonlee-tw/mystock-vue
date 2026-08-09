"""出廠過磅業務邏輯層（UC-002）

負責出廠過磅確認的核心商業邏輯。
淨重計算等領域規則透過 WeighTicket Entity 處理，Repository 只負責資料存取。
透過 UnitOfWork 存取 Repository，並統一控制交易邊界。
"""
import logging
from datetime import datetime

from backend.core.i18n import DEFAULT_LOCALE, translate
from backend.domain.entities.weigh_ticket import WeighTicket
from backend.domain.ports.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


def confirm_exit(uow: UnitOfWork, record, locale: str = DEFAULT_LOCALE) -> dict:
    """UC-002：出廠過磅確認（業務邏輯）。

    Domain 邏輯（淨重計算、退貨判斷）透過 WeighTicket Entity 完成，
    Repository 只接收計算結果進行資料更新。
    """
    now = datetime.now()

    exit_d = record.exitDate.strftime("%Y%m%d") if record.exitDate else now.strftime("%Y%m%d")
    exit_t = record.exitTime.strftime("%H%M%S") if record.exitTime else now.strftime("%H%M%S")

    weigth4 = int(record.exitWeightB1 or 0)
    is_return = bool(record.isReturn)

    # ── Domain Entity：取得入廠資訊並計算淨重 ──────────────────────────
    entry_info = uow.tickets.get_entry_info(record.ticketNo)
    a1 = entry_info.get("a1", 0)
    po_no = entry_info.get("poNo", "")

    ticket = WeighTicket(
        ticket_no=record.ticketNo,
        entry_weight_a1=a1,
        po_no=po_no,
    )
    net_weight = ticket.calculate_net_weight(weigth4, is_return)

    # ── 組裝 Repository 所需資料（含計算結果）─────────────────────────
    data = {
        **record.model_dump(exclude={"exitDate", "exitTime"}),
        "exitDate":  exit_d,
        "exitTime":  exit_t,
        "netWeight": net_weight,
        "a1":        a1,
        "poNo":      po_no,
    }

    uow.tickets.update_exit(record.ticketNo, data)
    uow.commit()

    msg_key = "EXIT_RETURN_SUCCESS" if is_return else "EXIT_CONFIRM_SUCCESS"
    log.info("[出廠確認] 磅單=%s B1=%s Kg 淨重=%s Kg 退貨=%s",
             record.ticketNo, record.exitWeightB1, net_weight, is_return)

    return {
        "status":    "success",
        "message":   translate(msg_key, locale, ticket_no=record.ticketNo),
        "netWeight": net_weight,
        "timestamp": now.isoformat(),
        "dbMode":    uow.db_mode,
    }
