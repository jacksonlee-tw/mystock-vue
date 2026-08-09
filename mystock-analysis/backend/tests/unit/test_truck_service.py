"""車輛清單 Service 單元測試

使用 MemoryUnitOfWork — 車輛資料源自 MemoryStore.entry_store。
"""
from backend.schemas.weighbridge import EntryRecord
from backend.services.entry_service import confirm_entry
from backend.services.truck_service import list_trucks


def _do_entry(uow, car_no, po_no="PO001"):
    record = EntryRecord(carNo=car_no, poNo=po_no, entryWeightA1=3000, scaleType="double")
    confirm_entry(uow, record, "zh-TW")


class TestListTrucks:

    def test_empty_when_no_entries(self, uow):
        result = list_trucks(uow)
        assert result["count"] == 0

    def test_lists_distinct_trucks(self, uow):
        _do_entry(uow, "TR-001")
        _do_entry(uow, "TR-002")
        _do_entry(uow, "TR-001")  # 重複車號

        result = list_trucks(uow)
        assert result["count"] == 2

    def test_keyword_filter(self, uow):
        _do_entry(uow, "AAA-111")
        _do_entry(uow, "BBB-222")

        result = list_trucks(uow, keyword="AAA")
        assert result["count"] == 1
        assert result["trucks"][0]["truckNo"] == "AAA-111"
