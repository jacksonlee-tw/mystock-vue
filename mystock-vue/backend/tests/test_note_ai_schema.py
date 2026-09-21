import unittest

from note_ai.schema import (
    ExtractedSymbol,
    ImageTranscription,
    NoteExtraction,
    normalize_topic_tags,
    transcription_to_markdown,
)


class TranscriptionToMarkdownTests(unittest.TestCase):
    def test_table_is_assembled_with_header_separator_and_rows(self):
        t = ImageTranscription(
            ref="image-1", kind="table", title="15檔晶片股",
            columns=["代號", "公司", "漲幅(%)"], rows=[["2303", "聯電", "5.76"], ["2330", "台積電", "1.44"]],
        )
        self.assertEqual(
            transcription_to_markdown(t),
            "| 代號 | 公司 | 漲幅(%) |\n| --- | --- | --- |\n| 2303 | 聯電 | 5.76 |\n| 2330 | 台積電 | 1.44 |",
        )

    def test_short_rows_are_padded_and_long_rows_truncated_to_column_count(self):
        t = ImageTranscription(ref="i", kind="table", columns=["A", "B"], rows=[["1"], ["1", "2", "3"]])
        lines = transcription_to_markdown(t).splitlines()
        self.assertEqual(lines[2], "| 1 |  |")
        self.assertEqual(lines[3], "| 1 | 2 |")

    def test_pipes_and_newlines_in_cells_cannot_break_the_table(self):
        t = ImageTranscription(ref="i", kind="table", columns=["名稱"], rows=[["a|b\nc"]])
        row = transcription_to_markdown(t).splitlines()[2]
        self.assertEqual(row, r"| a\|b c |")

    def test_text_kind_returns_the_text_verbatim_stripped(self):
        t = ImageTranscription(ref="i", kind="text", text="  一段文字  ")
        self.assertEqual(transcription_to_markdown(t), "一段文字")

    def test_table_without_columns_falls_back_to_text(self):
        t = ImageTranscription(ref="i", kind="table", columns=[], rows=[], text="沒有欄位")
        self.assertEqual(transcription_to_markdown(t), "沒有欄位")

    def test_empty_transcription_is_empty_string(self):
        self.assertEqual(transcription_to_markdown(ImageTranscription(ref="i", kind="text")), "")


class NormalizeTopicTagsTests(unittest.TestCase):
    def test_strips_dedupes_case_insensitively_and_drops_blank(self):
        self.assertEqual(normalize_topic_tags([" 記憶體 ", "記憶體", "AI", "ai", "", "  "]), ["記憶體", "AI"])

    def test_drops_hash_prefix_that_models_like_to_add(self):
        self.assertEqual(normalize_topic_tags(["#法人買超", "＃AI伺服器"]), ["法人買超", "AI伺服器"])

    def test_tags_longer_than_the_db_limit_are_dropped_not_truncated(self):
        # investment_note_tag.name 是 VARCHAR(30)；截斷會產生語意不明的標籤，直接丟掉
        self.assertEqual(normalize_topic_tags(["短", "字" * 31]), ["短"])

    def test_caps_the_count(self):
        self.assertEqual(len(normalize_topic_tags([f"t{i}" for i in range(20)])), 8)


class SchemaShapeTests(unittest.TestCase):
    def test_note_extraction_defaults_are_empty_so_partial_model_output_still_parses(self):
        e = NoteExtraction(subject="主旨")
        self.assertEqual((e.topic_tags, e.symbols, e.transcriptions, e.summary_sections), ([], [], [], []))

    def test_extracted_symbol_market_is_restricted(self):
        with self.assertRaises(ValueError):
            ExtractedSymbol(market="jp", symbol="7203", name="Toyota", evidence="x")


if __name__ == "__main__":
    unittest.main()
