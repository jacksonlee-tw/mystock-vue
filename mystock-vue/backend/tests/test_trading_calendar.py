import unittest
from datetime import datetime
from unittest import mock

from services import index_fetcher, trading_calendar
from services.trading_calendar import get_latest_expected_trading_date


class TwTradingDateTests(unittest.TestCase):
    """台股委派 index_fetcher.get_latest_expected_tw_trading_date()（規劃書 §3.2）；
    這裡驗證委派本身與幾個關鍵邊界情境，不重複該函式已涵蓋的完整行為。"""

    def setUp(self):
        patcher = mock.patch.object(index_fetcher, "load_no_trading_days", return_value=set())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_before_cutoff_falls_back_to_previous_trading_day(self):
        # 2026-09-24（四）09:00，未到 14:30 cutoff → 應回退到前一交易日 09/23（三）
        now = datetime(2026, 9, 24, 9, 0)
        self.assertEqual(get_latest_expected_trading_date("tw", now), "2026-09-23")

    def test_after_cutoff_uses_today(self):
        # 2026-09-24（四）15:00，已過 14:30 cutoff → 當天即為預期最新交易日
        now = datetime(2026, 9, 24, 15, 0)
        self.assertEqual(get_latest_expected_trading_date("tw", now), "2026-09-24")

    def test_weekend_falls_back_to_friday(self):
        # 2026-09-26（六）→ 回退到 09/25（五）
        now = datetime(2026, 9, 26, 15, 0)
        self.assertEqual(get_latest_expected_trading_date("tw", now), "2026-09-25")

    def test_known_no_trading_day_is_skipped(self):
        with mock.patch.object(index_fetcher, "load_no_trading_days", return_value={"2026-09-24"}):
            now = datetime(2026, 9, 24, 15, 0)
            self.assertEqual(get_latest_expected_trading_date("tw", now), "2026-09-23")


class UsTradingDateTests(unittest.TestCase):
    def test_before_cutoff_falls_back_to_previous_trading_day(self):
        # 2026-09-24（四）16:00 ET，未到 17:00 cutoff → 回退到 09/23（三）
        now = datetime(2026, 9, 24, 16, 0)
        self.assertEqual(get_latest_expected_trading_date("us", now), "2026-09-23")

    def test_after_cutoff_uses_today(self):
        now = datetime(2026, 9, 24, 18, 0)
        self.assertEqual(get_latest_expected_trading_date("us", now), "2026-09-24")

    def test_weekend_falls_back_to_friday(self):
        # 2026-09-26（六）→ 回退到 09/25（五）
        now = datetime(2026, 9, 26, 18, 0)
        self.assertEqual(get_latest_expected_trading_date("us", now), "2026-09-25")

    def test_nyse_holiday_is_skipped(self):
        # 2026-12-25（五）為聖誕節休市，且隔天 12/26、12/27 為週末 → 回退到 12/24（四）
        now = datetime(2026, 12, 25, 18, 0)
        self.assertEqual(get_latest_expected_trading_date("us", now), "2026-12-24")

    def test_crosses_year_boundary_around_new_year_holiday(self):
        # 2027-01-01（五）為元旦休市，前一天 2026-12-31（四）才是交易日
        now = datetime(2027, 1, 1, 18, 0)
        self.assertEqual(get_latest_expected_trading_date("us", now), "2026-12-31")


class UnsupportedMarketTests(unittest.TestCase):
    def test_unknown_market_raises(self):
        with self.assertRaises(ValueError):
            get_latest_expected_trading_date("jp", datetime(2026, 9, 24, 18, 0))


if __name__ == "__main__":
    unittest.main()
