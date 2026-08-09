"""入廠過磅 Service 單元測試（UC-001）

使用 MemoryUnitOfWork — 不需要 DB 連線。
"""
from backend.schemas.weighbridge import EntryRecord
from backend.services.entry_service import confirm_entry


def _make_entry_record(**overrides) -> EntryRecord:
    """建立入廠記錄 DTO（預設值填好，可覆寫）"""
    defaults = {
        "carNo": "ABC-1234",
        "poNo": "PO001",
        "entryWeightA1": 2500,
        "scaleType": "double",
        "materialName": "砂石料",
        "supplier": "台灣砂石有限公司",
    }
    defaults.update(overrides)
    return EntryRecord(**defaults)


class TestConfirmEntry:
    """UC-001：入廠過磅確認"""

    def test_success_returns_ticket_no(self, uow):
        record = _make_entry_record()
        result = confirm_entry(uow, record, "zh-TW")

        assert result["status"] == "success"
        assert result["ticketNo"]  # 非空磅單號
        assert result["dbMode"] == "memory"

    def test_ticket_stored_in_repository(self, uow):
        record = _make_entry_record(carNo="XYZ-5678", poNo="PO002")
        result = confirm_entry(uow, record, "zh-TW")

        ticket_no = result["ticketNo"]
        ticket = uow.tickets.get_ticket(ticket_no)
        assert ticket is not None
        assert ticket["truckNo"] == "XYZ-5678"
        assert ticket["poNo"] == "PO002"

    def test_sequential_ticket_numbers(self, uow):
        r1 = confirm_entry(uow, _make_entry_record(carNo="A-001"), "zh-TW")
        r2 = confirm_entry(uow, _make_entry_record(carNo="A-002"), "zh-TW")

        # 磅單號應遞增
        assert r1["ticketNo"] != r2["ticketNo"]
        assert r1["ticketNo"] < r2["ticketNo"]

    def test_weight_stored_correctly(self, uow):
        record = _make_entry_record(entryWeightA1=3000)
        result = confirm_entry(uow, record, "zh-TW")

        ticket_no = result["ticketNo"]
        entry_info = uow.tickets.get_entry_info(ticket_no)
        assert entry_info["a1"] == 3000

    def test_workflow_double_scale(self, uow):
        record = _make_entry_record(scaleType="double")
        result = confirm_entry(uow, record, "zh-TW")

        ticket = uow.tickets.get_ticket(result["ticketNo"])
        assert ticket is not None

    def test_entry_with_batch_and_ship(self, uow):
        record = _make_entry_record(batchNo="BATCH001", shipNo="SHIP01")
        result = confirm_entry(uow, record, "zh-TW")

        assert result["status"] == "success"
        ticket = uow.tickets.get_ticket(result["ticketNo"])
        assert ticket["batchNo"] == "BATCH001"
