import unittest

from note_ai.prompt import MAX_NOTE_TEXT_CHARS, PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt


class UserPromptTests(unittest.TestCase):
    def _build(self, **kw):
        args = dict(
            note_date="2026-09-20", subject="黃勳喊話 15檔晶片股強力表態", market="tw", symbol=None,
            text="![貼上圖片 1][image-1]", image_refs=["image-1"], skipped_image_count=0,
        )
        args.update(kw)
        return build_user_prompt(**args)

    def test_lists_the_image_refs_in_order(self):
        prompt = self._build(image_refs=["image-1", "image-2"])
        self.assertLess(prompt.index("image-1"), prompt.rindex("image-2"))
        self.assertIn("2 張", prompt)

    def test_no_images_says_so_instead_of_inviting_the_model_to_imagine_one(self):
        prompt = self._build(text="純文字", image_refs=[])
        self.assertIn("無附圖", prompt)

    def test_tells_the_model_when_images_were_dropped_by_the_cap(self):
        prompt = self._build(skipped_image_count=3)
        self.assertIn("3 張", prompt)
        self.assertIn("未附上", prompt)

    def test_includes_subject_date_and_note_text(self):
        prompt = self._build(text="今日觀察：記憶體")
        for expected in ("黃勳喊話 15檔晶片股強力表態", "2026-09-20", "今日觀察：記憶體"):
            self.assertIn(expected, prompt)

    def test_anchor_symbol_is_included_when_present(self):
        self.assertIn("2330", self._build(market="tw", symbol="2330"))

    def test_overlong_text_is_truncated_and_marked(self):
        prompt = self._build(text="字" * (MAX_NOTE_TEXT_CHARS + 500))
        self.assertLessEqual(prompt.count("字"), MAX_NOTE_TEXT_CHARS)
        self.assertIn("已截斷", prompt)


class SystemPromptTests(unittest.TestCase):
    def test_version_is_set(self):
        self.assertTrue(PROMPT_VERSION)

    def test_forbids_investment_advice_and_guessing_unreadable_cells(self):
        self.assertIn("不構成投資建議", SYSTEM_PROMPT)
        self.assertIn("不要猜", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
