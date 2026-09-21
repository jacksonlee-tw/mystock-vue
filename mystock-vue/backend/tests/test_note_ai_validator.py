import unittest

from note_ai.schema import ExtractedSymbol
from note_ai.validator import validate_symbols

MASTER = {
    ("tw", "2303"): "聯電",
    ("tw", "2330"): "台積電",
    ("tw", "3711"): "日月光投控",
    ("tw", "2449"): "京元電子",
    ("us", "NET"): "Cloudflare, Inc.",
}


class FakeRepo:
    def __init__(self, master=MASTER, fail=False):
        self.master, self.fail, self.search_calls = master, fail, []

    async def get_symbols(self, codes, market):
        if self.fail:
            raise ConnectionError("postgres down")
        return [{"symbol": c, "name": self.master[(market, c)]} for c in codes if (market, c) in self.master]

    async def search_symbols(self, query, market, limit=20):
        self.search_calls.append((query, market))
        return [{"symbol": c, "name": n} for (m, c), n in self.master.items() if m == market and query in n]


def sym(code, name, market="tw", evidence="圖中第1列"):
    return ExtractedSymbol(market=market, symbol=code, name=name, evidence=evidence)


class ValidateSymbolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_code_with_matching_name_is_verified(self):
        [v] = await validate_symbols([sym("2303", "聯電")], repo=FakeRepo())
        self.assertEqual((v.status, v.master_name, v.reason), ("verified", "聯電", None))

    async def test_fullwidth_spaces_from_newspaper_tables_do_not_break_matching(self):
        # 報紙表格常見「聯　電」「台積 電」這種排版空白
        [a, b] = await validate_symbols([sym("2303", "聯　電"), sym("2330", "台積 電")], repo=FakeRepo())
        self.assertEqual((a.status, b.status), ("verified", "verified"))

    async def test_name_abbreviation_is_accepted_by_containment(self):
        [v] = await validate_symbols([sym("3711", "日月光")], repo=FakeRepo())
        self.assertEqual(v.status, "verified")

    async def test_code_that_does_not_exist_is_not_found(self):
        [v] = await validate_symbols([sym("9999", "不存在公司")], repo=FakeRepo())
        self.assertEqual(v.status, "not_found")
        self.assertIn("9999", v.reason)

    async def test_wrong_company_for_code_is_name_mismatch_and_reports_master_name(self):
        # 幻覺的典型型態不是掰出不存在的公司，而是「公司對、代號記錯」
        [v] = await validate_symbols([sym("2330", "聯電")], repo=FakeRepo())
        self.assertEqual(v.status, "name_mismatch")
        self.assertEqual(v.master_name, "台積電")
        self.assertIn("台積電", v.reason)

    async def test_mismatch_suggests_the_code_found_by_name(self):
        [v] = await validate_symbols([sym("2330", "聯電")], repo=FakeRepo())
        self.assertEqual(v.suggestion, {"market": "tw", "symbol": "2303", "name": "聯電"})

    async def test_not_found_also_gets_a_suggestion_by_name(self):
        [v] = await validate_symbols([sym("2304", "京元電子")], repo=FakeRepo())
        self.assertEqual(v.status, "not_found")
        self.assertEqual(v.suggestion["symbol"], "2449")

    async def test_ambiguous_name_search_gives_no_suggestion(self):
        master = {("tw", "1101"): "台泥", ("tw", "1102"): "亞泥", ("tw", "1103"): "嘉泥", ("tw", "9998"): "別的"}
        [v] = await validate_symbols([sym("0000", "泥")], repo=FakeRepo(master))
        self.assertIsNone(v.suggestion)

    async def test_duplicates_are_merged_first_occurrence_wins(self):
        out = await validate_symbols([sym("2303", "聯電"), sym("2303", "聯電", evidence="第二次")], repo=FakeRepo())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].evidence, "圖中第1列")

    async def test_code_is_normalized_before_lookup(self):
        [v] = await validate_symbols([sym(" 2303.TW ", "聯電")], repo=FakeRepo())
        self.assertEqual((v.symbol, v.status), ("2303", "verified"))

    async def test_us_ticker_is_uppercased_and_looked_up_in_us_market(self):
        [v] = await validate_symbols([sym("net", "Cloudflare", market="us")], repo=FakeRepo())
        self.assertEqual((v.market, v.symbol, v.status), ("us", "NET", "verified"))

    async def test_master_unavailable_marks_everything_unverified_instead_of_pretending(self):
        # DATA_SOURCE=json、沒有 Postgres 時，不可假裝已驗證通過
        out = await validate_symbols([sym("2303", "聯電"), sym("2330", "台積電")], repo=FakeRepo(fail=True))
        self.assertEqual([v.status for v in out], ["unverified", "unverified"])
        self.assertIsNone(out[0].master_name)

    async def test_empty_or_blank_codes_are_dropped(self):
        self.assertEqual(await validate_symbols([sym("", "x"), sym("  ", "y")], repo=FakeRepo()), [])

    async def test_order_of_first_occurrence_is_preserved(self):
        out = await validate_symbols([sym("2330", "台積電"), sym("2303", "聯電")], repo=FakeRepo())
        self.assertEqual([v.symbol for v in out], ["2330", "2303"])


if __name__ == "__main__":
    unittest.main()
