"""磅單查詢與列印 Service 單元測試（UC-003 + 查詢）

使用 MemoryUnitOfWork — 不需要 DB 連線。
"""
import pytest

from backend.core.exceptions import AppException
from backend.schemas.weighbridge import EntryRecord
from backend.services.entry_service import confirm_entry
from backend.services.ticket_service import (
    reprint_ticket,
    get_ticket,
    list_today_tickets,
)


def _do_entry(uow, car_no="ABC-1234", po_no="PO001") -> str:
    """輔助：建立入廠紀錄並回傳磅單號"""
    record = EntryRecord(carNo=car_no, poNo=po_no, entryWeightA1=3000, scaleType="double")
    return confirm_entry(uow, record, "zh-TW")["ticketNo"]


class TestReprintTicket:
    """UC-003：重印磅單"""

    def test_reprint_increments_count(self, uow):
        ticket_no = _do_entry(uow)

        r1 = reprint_ticket(uow, ticket_no, "in", "zh-TW")
        assert r1["status"] == "success"
        assert r1["printCount"] == 1

        r2 = reprint_ticket(uow, ticket_no, "in", "zh-TW")
        assert r2["printCount"] == 2

    def test_reprint_empty_ticket_no_raises(self, uow):
        with pytest.raises(AppException) as exc_info:
            reprint_ticket(uow, "   ", "in", "zh-TW")
        assert exc_info.value.error_code == "TICKET_NO_EMPTY"


class TestGetTicket:
    """磅單查詢"""

    def test_get_existing_ticket(self, uow):
        ticket_no = _do_entry(uow, car_no="QUERY-001")
        result = get_ticket(uow, ticket_no, "zh-TW")

        assert result["status"] == "found"
        assert result["truckNo"] == "QUERY-001"

    def test_get_nonexistent_ticket_raises(self, uow):
        with pytest.raises(AppException) as exc_info:
            get_ticket(uow, "NONEXIST999", "zh-TW")
        assert exc_info.value.error_code == "TICKET_NOT_FOUND"
        assert exc_info.value.status_code == 404


class TestListTodayTickets:
    """當日磅單清單"""

    def test_empty_when_no_entries(self, uow):
        result = list_today_tickets(uow)
        assert result["count"] == 0
        assert result["tickets"] == []
        assert result["dbMode"] == "memory"

    def test_lists_entries_after_creation(self, uow):
        _do_entry(uow, car_no="T-001")
        _do_entry(uow, car_no="T-002")

        result = list_today_tickets(uow)
        assert result["count"] == 2
        truck_nos = {t["truckNo"] for t in result["tickets"]}
        assert truck_nos == {"T-001", "T-002"}
