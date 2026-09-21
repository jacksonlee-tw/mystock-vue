import threading
import unittest
from datetime import datetime
from unittest import mock

from services import fetcher

TODAY = datetime(2026, 9, 23)  # 星期三 → days=3 涵蓋 9/23、9/22、9/21（皆為平日）
NO_DATA = {"stat": "很抱歉，沒有符合條件的資料!"}

MI_INDEX_OK = {
    "stat": "OK",
    "tables": [{
        "title": "每日收盤行情(全部(不含權證、牛熊證))",
        "fields": ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
        "data": [["2330", "台積電", "1,000,000", "500", "900,000,000", "900.0", "910.0", "895.0", "905.0"]],
    }],
}
MI_MARGN_OK = {
    "stat": "OK",
    "tables": [{"data": []}, {"data": [["2330", "台積電"] + ["100"] * 13]}],
}
T86_FIELDS = [
    "證券代號", "證券名稱",
    "外陸資買賣超股數(不含外資自營商)", "外資自營商買賣超股數",
    "投信買賣超股數", "自營商買賣超股數", "三大法人買賣超股數",
]
T86_OK = {
    "stat": "OK",
    "fields": T86_FIELDS,
    "data": [["2330", "台積電", "3,000,000", "0", "1,000,000", "-500,000", "3,500,000"]],
}


def _date_of(url: str) -> str:
    return url.split("date=")[1][:8]


class FakeTwse:
    """依 URL 回應 TWSE 端點；記錄每個請求，並可對指定日期／端點覆寫回應。"""

    def __init__(self, overrides=None):
        self.overrides = overrides or {}
        self.requests = []
        self._lock = threading.Lock()

    def __call__(self, url, *args, **kwargs):
        endpoint = next(name for name in ("MI_INDEX", "MI_MARGN", "T86") if name in url)
        with self._lock:
            self.requests.append((endpoint, _date_of(url)))
        override = self.overrides.get((endpoint, _date_of(url)))
        if isinstance(override, Exception):
            raise override
        if override is not None:
            return override
        return {"MI_INDEX": MI_INDEX_OK, "MI_MARGN": MI_MARGN_OK, "T86": T86_OK}[endpoint]

    def count(self, endpoint=None, date=None):
        return sum(1 for e, d in self.requests
                   if (endpoint is None or e == endpoint) and (date is None or d == date))


class FetchMarketDataTests(unittest.TestCase):
    def setUp(self):
        self.no_trading = set()
        self.saved_no_trading = []
        self.existing = {}
        patches = [
            mock.patch.object(fetcher, "load_stock_json", side_effect=lambda sid, market="tw": self.existing.get(sid, {})),
            mock.patch.object(fetcher, "load_no_trading_days", side_effect=lambda: set(self.no_trading)),
            mock.patch.object(fetcher, "save_no_trading_days", side_effect=self.saved_no_trading.append),
            mock.patch.object(fetcher, "dual_write_no_trading_days"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _run(self, twse, workers=3):
        with mock.patch.object(fetcher, "twse_get_json", twse):
            return fetcher.fetch_market_data(["2330"], {"2330": 3}, today=TODAY, max_workers=workers)

    def test_each_missing_day_costs_exactly_three_requests_and_yields_a_merged_record(self):
        twse = FakeTwse()
        df, quote_lookup, _ = self._run(twse)

        self.assertEqual(len(twse.requests), 9)  # 3 天 × (MI_INDEX + MI_MARGN + T86)
        self.assertEqual(len(df), 3)
        row = df[df["日期"] == "2026-09-22"].iloc[0]
        self.assertEqual(row["收盤價"], 905.0)          # 行情來自 MI_INDEX
        self.assertEqual(row["外資買賣超(張)"], 3000)     # 法人來自 T86
        self.assertEqual(row["融資餘額(張)"], 100)        # 融資券來自 MI_MARGN
        self.assertEqual(quote_lookup["2330"]["2026-09-22"]["收盤價"], 905.0)

    def test_known_no_trading_days_are_not_requested(self):
        self.no_trading = {"2026-09-22"}
        twse = FakeTwse()
        self._run(twse)
        self.assertEqual(twse.count(date="20260922"), 0)
        self.assertEqual(twse.count(date="20260923"), 3)

    def test_day_with_complete_quote_and_margin_is_skipped_entirely(self):
        self.existing["2330"] = {"2026-09-21": {"close": 900.0, "margin_balance": 5}}
        twse = FakeTwse()
        self._run(twse)
        self.assertEqual(twse.count(date="20260921"), 0)

    def test_day_with_only_quote_missing_skips_institutional_endpoints(self):
        # 有法人融資券、缺行情 → 只需補 MI_INDEX
        self.existing["2330"] = {"2026-09-21": {"close": 0, "margin_balance": 5}}
        twse = FakeTwse()
        self._run(twse)
        self.assertEqual(twse.count("MI_INDEX", "20260921"), 1)
        self.assertEqual(twse.count("MI_MARGN", "20260921"), 0)
        self.assertEqual(twse.count("T86", "20260921"), 0)

    def test_no_data_response_on_past_day_is_recorded_as_no_trading(self):
        twse = FakeTwse({("T86", "20260921"): NO_DATA, ("MI_INDEX", "20260921"): NO_DATA})
        self._run(twse)
        self.assertEqual(self.saved_no_trading, [{"2026-09-21"}])

    def test_unrecognised_stat_is_not_treated_as_holiday(self):
        # 被限流／系統忙碌之類的非 OK 回應不等於休市；誤記會讓該日永遠被略過
        twse = FakeTwse({("T86", "20260921"): {"stat": "系統忙碌，請稍後再試"}})
        self._run(twse)
        self.assertEqual(self.saved_no_trading, [])

    def test_no_data_today_is_not_recorded_as_no_trading(self):
        # 當天資料收盤後才會公布，查無資料不能當成休市
        twse = FakeTwse({("T86", "20260923"): NO_DATA})
        self._run(twse)
        self.assertEqual(self.saved_no_trading, [])

    def test_one_failing_day_does_not_abort_the_others(self):
        twse = FakeTwse({("T86", "20260922"): ConnectionError("dropped")})
        df, _, _ = self._run(twse)
        self.assertEqual(sorted(df["日期"]), ["2026-09-21", "2026-09-23"])

    def test_sequential_and_concurrent_runs_produce_the_same_data(self):
        df_seq, _, _ = self._run(FakeTwse(), workers=1)
        df_par, _, _ = self._run(FakeTwse(), workers=3)
        key = lambda df: sorted(map(tuple, df.sort_values("日期").astype(str).values.tolist()))
        self.assertEqual(key(df_seq), key(df_par))


class HolidayCalendarTests(unittest.TestCase):
    ROWS = [
        ["2026-01-01", "中華民國開國紀念日", "依規定放假1日。"],
        ["2026-01-02", "國曆新年開始交易日", "國曆新年開始交易。"],     # 交易日，不可收
        ["2026-02-11", "農曆春節前最後交易日", "農曆春節前最後交易。"],   # 交易日，不可收
        ["2026-02-12", "市場無交易，僅辦理結算交割作業", ""],
        ["2026-02-15", "農曆除夕及春節", "依規定放假"],                  # 星期日，平日邏輯本來就會排除
        ["2025-12-31", "他年資料", ""],                                  # 端點對未知年份會回退到今年，年份不符要丟掉
    ]

    def test_only_weekday_non_trading_rows_of_the_requested_year_are_kept(self):
        self.assertEqual(
            fetcher.parse_holiday_dates(self.ROWS, 2026),
            {"2026-01-01", "2026-02-12"},
        )

    def test_sync_merges_new_holidays_and_persists_only_when_changed(self):
        saved = []
        response = {"stat": "ok", "data": self.ROWS}
        with mock.patch.object(fetcher, "twse_get_json", return_value=response) as get, \
             mock.patch.object(fetcher, "load_no_trading_days", return_value={"2026-01-01"}), \
             mock.patch.object(fetcher, "save_no_trading_days", side_effect=saved.append), \
             mock.patch.object(fetcher, "dual_write_no_trading_days") as dual:
            added = fetcher.sync_holiday_calendar(days=30, today=datetime(2026, 3, 1))

        self.assertIn("date=20260101", get.call_args.args[0])   # 端點用 date= 而非 queryYear=
        self.assertEqual(added, 1)
        self.assertEqual(saved, [{"2026-01-01", "2026-02-12"}])
        dual.assert_called_once_with("tw", {"2026-02-12"}, source="calendar")

    def test_sync_is_best_effort_when_the_endpoint_fails(self):
        with mock.patch.object(fetcher, "twse_get_json", side_effect=ConnectionError("down")), \
             mock.patch.object(fetcher, "load_no_trading_days", return_value=set()), \
             mock.patch.object(fetcher, "save_no_trading_days") as save:
            self.assertEqual(fetcher.sync_holiday_calendar(days=30, today=datetime(2026, 3, 1)), 0)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
