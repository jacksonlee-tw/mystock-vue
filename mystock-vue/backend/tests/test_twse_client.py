import threading
import time
import unittest
from unittest import mock

import requests

from services.twse_client import AdaptiveRateLimiter, twse_get_json


class FakeClock:
    """可控時鐘：sleep 只推進時間，不真的等待，讓限流器測試瞬間跑完。"""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _limiter(clock, **overrides):
    params = dict(
        start_interval=2.0, min_interval=1.0, max_interval=8.0,
        speedup_after=3, speedup_step=0.5,
        clock=clock.monotonic, sleep=clock.sleep,
    )
    params.update(overrides)
    return AdaptiveRateLimiter(**params)


class AdaptiveRateLimiterTests(unittest.TestCase):
    def test_first_acquire_is_immediate_then_spaced_by_interval(self):
        clock = FakeClock()
        limiter = _limiter(clock)
        for _ in range(3):
            limiter.acquire()
        # 第一次不等；之後每次要間隔 2 秒
        self.assertEqual(clock.sleeps, [2.0, 2.0])

    def test_no_wait_when_caller_was_already_slower_than_interval(self):
        clock = FakeClock()
        limiter = _limiter(clock)
        limiter.acquire()
        clock.now += 5.0  # 呼叫端自己就隔了 5 秒
        limiter.acquire()
        self.assertEqual(clock.sleeps, [])

    def test_throttle_doubles_interval_up_to_max(self):
        clock = FakeClock()
        limiter = _limiter(clock)
        for expected in (4.0, 8.0, 8.0):
            limiter.on_throttle(cooldown=0)
            self.assertEqual(limiter.interval, expected)

    def test_throttle_cooldown_delays_the_next_acquire_for_every_caller(self):
        clock = FakeClock()
        limiter = _limiter(clock)
        limiter.acquire()
        limiter.on_throttle(cooldown=10.0)
        limiter.acquire()
        self.assertGreaterEqual(clock.sleeps[-1], 10.0)

    def test_consecutive_successes_speed_up_but_never_below_floor(self):
        clock = FakeClock()
        limiter = _limiter(clock)  # 2.0 → 每連續 3 次成功降 0.5，下限 1.0
        for _ in range(3):
            limiter.on_success()
        self.assertEqual(limiter.interval, 1.5)
        for _ in range(30):
            limiter.on_success()
        self.assertEqual(limiter.interval, 1.0)

    def test_throttle_resets_success_streak(self):
        clock = FakeClock()
        limiter = _limiter(clock)
        limiter.on_success()
        limiter.on_success()
        limiter.on_throttle(cooldown=0)  # 間隔變 4.0，連勝歸零
        limiter.on_success()
        self.assertEqual(limiter.interval, 4.0)

    def test_concurrent_callers_get_distinct_spaced_slots(self):
        limiter = AdaptiveRateLimiter(start_interval=0.05, min_interval=0.05, max_interval=1.0)
        stamps = []
        lock = threading.Lock()

        def worker():
            limiter.acquire()
            with lock:
                stamps.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stamps.sort()
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        # 即使 5 條執行緒同時出發，放行時間點也必須彼此相隔（容忍排程抖動）
        self.assertTrue(all(gap >= 0.035 for gap in gaps), gaps)


class TwseGetJsonTests(unittest.TestCase):
    def _response(self, payload=None, json_error=None):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        if json_error:
            resp.json.side_effect = json_error
        else:
            resp.json.return_value = payload
        return resp

    def test_returns_json_and_reports_success(self):
        session, limiter = mock.Mock(), mock.Mock()
        session.get.return_value = self._response({"stat": "OK"})
        self.assertEqual(twse_get_json("http://x", session=session, limiter=limiter), {"stat": "OK"})
        limiter.acquire.assert_called_once()
        limiter.on_success.assert_called_once()
        limiter.on_throttle.assert_not_called()

    def test_retries_after_connection_error_and_penalizes_limiter(self):
        session, limiter = mock.Mock(), mock.Mock()
        session.get.side_effect = [
            requests.exceptions.ConnectionError("dropped"),
            self._response({"stat": "OK"}),
        ]
        result = twse_get_json("http://x", session=session, limiter=limiter)
        self.assertEqual(result, {"stat": "OK"})
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(limiter.acquire.call_count, 2)  # 重試也要重新排隊，不可繞過限流
        limiter.on_throttle.assert_called_once()

    def test_non_json_body_counts_as_throttle_signal(self):
        # 被擋時 TWSE 常回 HTML 而非 JSON，json() 會拋 ValueError
        session, limiter = mock.Mock(), mock.Mock()
        session.get.side_effect = [
            self._response(json_error=ValueError("not json")),
            self._response({"stat": "OK"}),
        ]
        self.assertEqual(twse_get_json("http://x", session=session, limiter=limiter), {"stat": "OK"})
        limiter.on_throttle.assert_called_once()

    def test_raises_after_retries_exhausted(self):
        session, limiter = mock.Mock(), mock.Mock()
        session.get.side_effect = requests.exceptions.Timeout("slow")
        with self.assertRaises(requests.exceptions.Timeout):
            twse_get_json("http://x", max_retries=3, session=session, limiter=limiter)
        self.assertEqual(session.get.call_count, 3)
        limiter.on_success.assert_not_called()


if __name__ == "__main__":
    unittest.main()
