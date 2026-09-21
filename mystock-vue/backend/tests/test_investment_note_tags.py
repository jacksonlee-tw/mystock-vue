import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from repositories.investment_note_repository import InvestmentNoteRepository
from services.investment_note_service import (
    MAX_TAG_LEN, MAX_TAGS, _normalize_tag_colors, _normalize_tag_names,
)


class NormalizeTagNamesTests(unittest.TestCase):
    def test_strips_and_dedupes_case_insensitively_keeping_first_spelling(self):
        self.assertEqual(_normalize_tag_names([" AI ", "ai", "", "  ", "記憶體"]), ["AI", "記憶體"])

    def test_none_or_empty_is_empty(self):
        self.assertEqual(_normalize_tag_names(None), [])
        self.assertEqual(_normalize_tag_names([]), [])

    def test_room_for_a_fifteen_stock_table_plus_topic_tags(self):
        # 報紙「15 檔晶片股」＋幾個主題標籤：舊上限 10 會無聲丟掉一半
        names = [str(2300 + i) for i in range(15)] + ["晶片", "法人買超", "AI"]
        self.assertEqual(_normalize_tag_names(names), names)

    def test_over_the_limit_raises_instead_of_silently_truncating(self):
        with self.assertRaises(ValueError) as ctx:
            _normalize_tag_names([f"t{i}" for i in range(MAX_TAGS + 1)])
        self.assertIn(str(MAX_TAGS), str(ctx.exception))

    def test_duplicates_do_not_count_toward_the_limit(self):
        names = ["a"] * (MAX_TAGS * 2) + ["b"]
        self.assertEqual(_normalize_tag_names(names), ["a", "b"])

    def test_tag_longer_than_the_db_column_is_a_400_style_error_not_a_db_500(self):
        with self.assertRaises(ValueError) as ctx:
            _normalize_tag_names(["字" * (MAX_TAG_LEN + 1)])
        self.assertIn(str(MAX_TAG_LEN), str(ctx.exception))

    def test_tag_of_exactly_the_max_length_is_fine(self):
        self.assertEqual(len(_normalize_tag_names(["字" * MAX_TAG_LEN])), 1)


class NormalizeTagColorsTests(unittest.TestCase):
    def test_keys_are_lowercased_to_match_case_insensitive_tag_names(self):
        self.assertEqual(_normalize_tag_colors({"NET": "sky"}), {"net": "sky"})

    def test_unknown_color_is_rejected(self):
        with self.assertRaises(ValueError):
            _normalize_tag_colors({"2330": "hotpink"})

    def test_none_is_empty(self):
        self.assertEqual(_normalize_tag_colors(None), {})


def _repo(existing: dict):
    """existing: {lower_name: tag}；不需要真的資料庫，只驗證 get_or_create_tags 的取色邏輯。"""
    session = MagicMock()
    session.flush = AsyncMock()
    repo = InvestmentNoteRepository(session)
    repo.get_tag_by_name = AsyncMock(side_effect=lambda name: existing.get(name.lower()))
    return repo, session


class GetOrCreateTagsColorTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_tag_gets_the_requested_color(self):
        repo, session = _repo({})
        [tag] = await repo.get_or_create_tags(["2330"], colors={"2330": "sky"})
        self.assertEqual(tag.color, "sky")
        session.add.assert_called_once()

    async def test_new_tag_without_a_color_keeps_the_default(self):
        repo, _ = _repo({})
        [tag] = await repo.get_or_create_tags(["晶片"])
        self.assertIn(tag.color, (None, "slate"))  # 未指定 → 交給 DB／ORM 預設 slate

    async def test_existing_default_colored_tag_is_upgraded(self):
        # AI 診股流程早就把代號當成 slate 標籤建過了，這裡要讓它升級成代號色
        existing = SimpleNamespace(id=1, name="2330", color="slate")
        repo, _ = _repo({"2330": existing})
        await repo.get_or_create_tags(["2330"], colors={"2330": "sky"})
        self.assertEqual(existing.color, "sky")

    async def test_existing_tag_with_a_deliberate_color_is_never_recolored(self):
        existing = SimpleNamespace(id=2, name="AI生成報告", color="amber")
        repo, _ = _repo({"ai生成報告": existing})
        await repo.get_or_create_tags(["AI生成報告"], colors={"ai生成報告": "sky"})
        self.assertEqual(existing.color, "amber")

    async def test_color_lookup_is_case_insensitive(self):
        repo, _ = _repo({})
        [tag] = await repo.get_or_create_tags(["NET"], colors={"net": "sky"})
        self.assertEqual(tag.color, "sky")


if __name__ == "__main__":
    unittest.main()
