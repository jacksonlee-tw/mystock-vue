import unittest
from unittest.mock import patch

from services import scheduler


class SchedulerOrderTests(unittest.TestCase):
    def test_tw_fetches_indices_first(self):
        calls = []

        with (
            patch.object(scheduler, "_fetch_indices", side_effect=lambda market: calls.append(f"index:{market}")),
            patch(
                "services.market_fetcher.market_fetcher.run_daily_pipeline",
                side_effect=lambda: calls.append("market:tw"),
            ),
            patch(
                "services.exchange_rate_fetcher.fetch_exchange_rates_now",
                side_effect=lambda **kwargs: calls.append("fx"),
            ),
            patch.object(
                scheduler,
                "_run_if_idle",
                side_effect=lambda market, fetch_fn: calls.append(f"stock:{market}"),
            ),
        ):
            scheduler._scheduled_tw()

        self.assertEqual(calls, ["index:tw", "market:tw", "fx", "stock:tw"])

    def test_us_fetches_indices_first(self):
        calls = []

        with (
            patch.object(scheduler, "_fetch_indices", side_effect=lambda market: calls.append(f"index:{market}")),
            patch.object(
                scheduler,
                "_run_if_idle",
                side_effect=lambda market, fetch_fn: calls.append(f"stock:{market}"),
            ),
        ):
            scheduler._scheduled_us()

        self.assertEqual(calls, ["index:us", "stock:us"])


if __name__ == "__main__":
    unittest.main()
