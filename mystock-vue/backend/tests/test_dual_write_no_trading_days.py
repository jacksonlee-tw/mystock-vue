import unittest
from datetime import date
from unittest import mock

from db import dual_write
from repositories.stock_repository import StockRepository


class DualWriteNoTradingDaysTests(unittest.TestCase):
    def _call(self, *args, **kwargs):
        with mock.patch.object(StockRepository, "add_no_trading_days_sync") as add:
            dual_write.dual_write_no_trading_days(*args, **kwargs)
        return add

    def test_source_defaults_to_probed(self):
        add = self._call("tw", ["2026-09-21"])
        add.assert_called_once_with("tw", {date(2026, 9, 21)}, "probed")

    def test_accepts_explicit_source(self):
        # market_fetcher 以 source="probed" 呼叫；休市日曆同步以 "calendar" 呼叫（見 V2 migration 註解）
        add = self._call("tw", ["2026-09-21"], source="calendar")
        add.assert_called_once_with("tw", {date(2026, 9, 21)}, "calendar")

    def test_empty_dates_is_a_noop(self):
        add = self._call("tw", [])
        add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
