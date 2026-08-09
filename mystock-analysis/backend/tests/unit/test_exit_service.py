"""出廠過磅 Service 單元測試（UC-002）

使用 MemoryUnitOfWork — 不需要 DB 連線。
先建立入廠紀錄，再測試出廠邏輯。
"""
from backend.schemas.weighbridge import EntryRecord, ExitRecord
from backend.services.entry_service import confirm_entry
from backend.services.exit_service import confirm_exit


def _do_entry(uow, car_no="ABC-1234", po_no="PO001", weight=5000) -> str:
    """輔助：建立入廠紀錄並回傳磅單號"""
    record = EntryRecord(carNo=car_no, poNo=po_no, entryWeightA1=weight, scaleType="double")
    result = confirm_entry(uow, record, "zh-TW")
    return result["ticketNo"]


class TestConfirmExit:
    """UC-002：出廠過磅確認"""

    def test_normal_exit_net_weight(self, uow):
        ticket_no = _do_entry(uow, weight=5000)

        record = ExitRecord(ticketNo=ticket_no, exitWeightB1=2000)
        result = confirm_exit(uow, record, "zh-TW")

        assert result["status"] == "success"
        assert result["netWeight"] == 3000  # 5000 - 2000

    def test_return_net_weight_zero(self, uow):
        ticket_no = _do_entry(uow, weight=5000)

        record = ExitRecord(ticketNo=ticket_no, exitWeightB1=2000, isReturn=True)
        result = confirm_exit(uow, record, "zh-TW")

        assert result["netWeight"] == 0  # 退貨淨重為 0

    def test_exit_heavier_than_entry(self, uow):
        """出廠重量 > 入廠重量時，淨重 = 0（不為負）"""
        ticket_no = _do_entry(uow, weight=1000)

        record = ExitRecord(ticketNo=ticket_no, exitWeightB1=3000)
        result = confirm_exit(uow, record, "zh-TW")

        assert result["netWeight"] == 0  # max(1000 - 3000, 0) = 0

    def test_exit_updates_ticket(self, uow):
        ticket_no = _do_entry(uow, weight=5000)

        record = ExitRecord(ticketNo=ticket_no, exitWeightB1=2000)
        confirm_exit(uow, record, "zh-TW")

        ticket = uow.tickets.get_ticket(ticket_no)
        assert ticket is not None
        assert ticket["status"] == "completed"

    def test_exit_dbmode_memory(self, uow):
        ticket_no = _do_entry(uow, weight=5000)

        record = ExitRecord(ticketNo=ticket_no, exitWeightB1=2000)
        result = confirm_exit(uow, record, "zh-TW")

        assert result["dbMode"] == "memory"
