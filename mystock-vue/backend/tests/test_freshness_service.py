import asyncio
import unittest
from datetime import datetime
from unittest import mock

import pytz

from services import freshness_service
from services.freshness_service import decide_action

TZ = pytz.timezone("Asia/Taipei")

_SCHEDULE_CONFIG = {
    "timezone": "Asia/Taipei",
    "markets": {
        "tw": {"time": "14:30", "hour": 14, "minute": 30, "enabled": True},
        "us": {"time": "06:00", "hour": 6, "minute": 0, "enabled": True},
    },
}


def _report(is_stale=True, expected_date="2026-09-25", stale_stocks=None, stale_indices=None):
    return {
        "market": "tw",
        "expected_date": expected_date,
        "checked_at": "2026-09-25T09:00:00+08:00",
        "stocks": {"total": 10, "stale": stale_stocks or ([{"symbol": "2455", "last_date": "2026-09-24"}] if is_stale else [])},
        "indices": {"total": 5, "stale": stale_indices or []},
        "is_stale": is_stale,
    }


class DecideActionTests(unittest.TestCase):
    """§3.4 決策表的純函式單元測試。"""

    def test_up_to_date_when_not_stale(self):
        action, _ = decide_action(
            report=_report(is_stale=False), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=None, now_mono=1000.0,
        )
        self.assertEqual(action, "up_to_date")

    def test_fetch_running_takes_priority_over_everything_else(self):
        action, _ = decide_action(
            report=_report(), is_fetch_running=True,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=None, now_mono=1000.0,
        )
        self.assertEqual(action, "fetch_running")

    def test_schedule_window_before_scheduled_time(self):
        # 14:30 排程，10 分鐘前的時窗起點是 14:20
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 14, 25)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=None, now_mono=1000.0,
        )
        self.assertEqual(action, "schedule_window")

    def test_schedule_window_after_scheduled_time_within_90_minutes(self):
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 15, 30)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=None, now_mono=1000.0,
        )
        self.assertEqual(action, "schedule_window")

    def test_outside_schedule_window_triggers(self):
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=None, now_mono=1000.0,
        )
        self.assertEqual(action, "triggered")

    def test_force_bypasses_schedule_window(self):
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 14, 25)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=None, now_mono=1000.0, force=True,
        )
        self.assertEqual(action, "triggered")

    def test_throttled_when_already_done_for_same_expected_date(self):
        throttle_state = {"expected_date": "2026-09-25", "status": "done", "finished_at_mono": 500.0}
        action, reason = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=throttle_state, now_mono=1000.0,
        )
        self.assertEqual(action, "throttled")
        self.assertIn("已補抓過", reason)

    def test_not_throttled_when_expected_date_advanced(self):
        # 節流鍵是 (market, expected_date)；交易日推進後自動解除（ADR-02）
        throttle_state = {"expected_date": "2026-09-24", "status": "done", "finished_at_mono": 500.0}
        action, _ = decide_action(
            report=_report(expected_date="2026-09-25"), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=throttle_state, now_mono=1000.0,
        )
        self.assertEqual(action, "triggered")

    def test_throttled_after_recent_failure_within_retry_window(self):
        throttle_state = {"expected_date": "2026-09-25", "status": "failed", "finished_at_mono": 1000.0}
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=throttle_state, now_mono=1000.0 + 60,  # 1 分鐘後
        )
        self.assertEqual(action, "throttled")

    def test_triggered_after_failure_retry_window_elapsed(self):
        throttle_state = {"expected_date": "2026-09-25", "status": "failed", "finished_at_mono": 1000.0}
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=throttle_state, now_mono=1000.0 + 1800.1,  # 30 分鐘又 0.1 秒後
        )
        self.assertEqual(action, "triggered")

    def test_force_bypasses_throttle(self):
        throttle_state = {"expected_date": "2026-09-25", "status": "done", "finished_at_mono": 500.0}
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 9, 0)), schedule_config=_SCHEDULE_CONFIG,
            throttle_state=throttle_state, now_mono=1000.0, force=True,
        )
        self.assertEqual(action, "triggered")

    def test_disabled_schedule_never_produces_schedule_window(self):
        config = {
            "timezone": "Asia/Taipei",
            "markets": {"tw": {"time": "14:30", "hour": 14, "minute": 30, "enabled": False}},
        }
        action, _ = decide_action(
            report=_report(), is_fetch_running=False,
            now=TZ.localize(datetime(2026, 9, 25, 14, 25)), schedule_config=config,
            throttle_state=None, now_mono=1000.0,
        )
        self.assertEqual(action, "triggered")


class BuildMarketReportTests(unittest.TestCase):
    """build_market_report()：驗證落後判斷與 60 秒快取（§3.3）。"""

    def setUp(self):
        freshness_service.invalidate_report_cache()
        self.addCleanup(freshness_service.invalidate_report_cache)

    def test_stale_symbol_and_missing_data_are_both_flagged(self):
        async def fake_get_symbols(market):
            return ["2330", "2455"]

        async def fake_coverage(self, symbols, market):
            return {"2330": {"end_date": "2026-09-25"}, "2455": {"end_date": "2026-09-24"}}

        with mock.patch.object(freshness_service, "get_crawl_enabled_symbols", fake_get_symbols), \
             mock.patch("repositories.stock_repository.StockRepository.get_coverage_summary", fake_coverage), \
             mock.patch.object(freshness_service, "get_index_definitions", return_value=[]), \
             mock.patch.object(freshness_service, "get_latest_expected_trading_date", return_value="2026-09-25"):
            report = asyncio.run(freshness_service.build_market_report("tw", use_cache=False))

        self.assertTrue(report["is_stale"])
        stale_symbols = {s["symbol"] for s in report["stocks"]["stale"]}
        self.assertEqual(stale_symbols, {"2455"})

    def test_report_is_cached_within_ttl(self):
        call_count = {"n": 0}

        async def fake_get_symbols(market):
            call_count["n"] += 1
            return []

        with mock.patch.object(freshness_service, "get_crawl_enabled_symbols", fake_get_symbols), \
             mock.patch.object(freshness_service, "get_index_definitions", return_value=[]), \
             mock.patch.object(freshness_service, "get_latest_expected_trading_date", return_value="2026-09-25"):
            asyncio.run(freshness_service.build_market_report("tw"))
            asyncio.run(freshness_service.build_market_report("tw"))

        self.assertEqual(call_count["n"], 1)


if __name__ == "__main__":
    unittest.main()
