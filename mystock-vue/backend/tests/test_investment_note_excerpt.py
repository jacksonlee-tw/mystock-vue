import unittest

from repositories.investment_note_repository import EXCERPT_LENGTH, _to_excerpt

B64 = "data:image/webp;base64," + "A" * 5000


def _excerpt(content: str) -> str:
    return _to_excerpt({"id": 1, "content": content})["content_excerpt"]


class ToExcerptTests(unittest.TestCase):
    def test_plain_text_is_truncated_as_before(self):
        self.assertEqual(_excerpt("短內容"), "短內容")
        long = "字" * (EXCERPT_LENGTH + 10)
        self.assertEqual(_excerpt(long), "字" * EXCERPT_LENGTH + "…")

    def test_reference_style_pasted_image_definition_is_dropped(self):
        content = f"# 觀察\n\n![貼上圖片 1][image-1]\n\n結論\n\n[image-1]: {B64}"
        self.assertEqual(_excerpt(content), "# 觀察\n\n![貼上圖片 1][image-1]\n\n結論")

    def test_definition_is_dropped_with_crlf_line_endings(self):
        # `\r` 不是 [ \t]，MULTILINE 的 `$` 也不匹配 `\r` 前，舊 regex 在 CRLF 下整段剝不掉，
        # 摘要會變成 240 字的 base64。textarea 會正規化成 LF，但直接打 API 的內容不會。
        content = f"# 觀察\r\n\r\n![貼上圖片 1][image-1]\r\n\r\n結論\r\n\r\n[image-1]: {B64}\r\n"
        self.assertNotIn("base64", _excerpt(content))

    def test_definition_is_dropped_when_not_last_line(self):
        content = f"結論\n\n[image-1]: {B64}\n\n[image-2]: {B64}\n"
        self.assertEqual(_excerpt(content), "結論")

    def test_blank_lines_left_by_stripping_are_collapsed(self):
        content = f"第一段\n\n[image-1]: {B64}\n\n[image-2]: {B64}\n\n第二段"
        self.assertEqual(_excerpt(content), "第一段\n\n第二段")

    def test_inline_data_uri_image_is_replaced_with_placeholder(self):
        excerpt = _excerpt(f"看圖 ![表格]({B64}) 後續")
        self.assertNotIn("base64", excerpt)
        self.assertIn("看圖", excerpt)
        self.assertIn("後續", excerpt)

    def test_regular_image_url_is_kept(self):
        self.assertEqual(_excerpt("![a](https://x.test/a.png)"), "![a](https://x.test/a.png)")


if __name__ == "__main__":
    unittest.main()
