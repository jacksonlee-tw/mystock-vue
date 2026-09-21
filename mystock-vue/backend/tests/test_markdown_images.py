import base64
import unittest

from core.markdown_images import (
    EmbeddedImage,
    extract_embedded_images,
    split_embedded_images,
    strip_embedded_images,
)

PNG_B64 = base64.b64encode(b"\x89PNG-fake-bytes").decode()
WEBP_B64 = base64.b64encode(b"RIFF-fake-webp").decode()


def _webp(n: int = 1) -> str:
    return f"[image-{n}]: data:image/webp;base64,{WEBP_B64}"


class ExtractEmbeddedImagesTests(unittest.TestCase):
    def test_reference_style_definitions_are_extracted_in_order(self):
        content = f"內文 ![貼上圖片 1][image-1] ![貼上圖片 2][image-2]\n\n{_webp(1)}\n\n[image-2]: data:image/png;base64,{PNG_B64}\n"
        images = extract_embedded_images(content)
        self.assertEqual([i.ref for i in images], ["image-1", "image-2"])
        self.assertEqual([i.mime_type for i in images], ["image/webp", "image/png"])
        self.assertEqual(images[0].data, b"RIFF-fake-webp")
        self.assertEqual(images[1].data, b"\x89PNG-fake-bytes")

    def test_inline_data_uri_images_are_extracted_with_generated_ref(self):
        images = extract_embedded_images(f"看圖 ![表格](data:image/webp;base64,{WEBP_B64}) 完")
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].ref, "inline-1")
        self.assertEqual(images[0].mime_type, "image/webp")

    def test_crlf_content_is_supported(self):
        content = f"內文\r\n\r\n{_webp(1)}\r\n"
        self.assertEqual(len(extract_embedded_images(content)), 1)

    def test_unsupported_mime_types_are_skipped(self):
        content = f"[image-1]: data:image/svg+xml;base64,{WEBP_B64}\n\n{_webp(2)}"
        images = extract_embedded_images(content)
        self.assertEqual([i.ref for i in images], ["image-2"])

    def test_malformed_base64_is_skipped_instead_of_raising(self):
        content = "[image-1]: data:image/webp;base64,@@not-base64@@\n"
        self.assertEqual(extract_embedded_images(content), [])

    def test_regular_urls_are_not_images_we_can_send(self):
        self.assertEqual(extract_embedded_images("![a](https://x.test/a.png)"), [])

    def test_returns_embedded_image_dataclass(self):
        image = extract_embedded_images(_webp(1))[0]
        self.assertIsInstance(image, EmbeddedImage)


class SplitEmbeddedImagesTests(unittest.TestCase):
    def test_text_keeps_reference_markers_but_drops_base64(self):
        content = f"# 觀察\n\n![貼上圖片 1][image-1]\n\n結論\n\n{_webp(1)}\n"
        images, text = split_embedded_images(content)
        self.assertEqual(len(images), 1)
        self.assertIn("![貼上圖片 1][image-1]", text)
        self.assertNotIn("base64", text)
        self.assertEqual(text, "# 觀察\n\n![貼上圖片 1][image-1]\n\n結論")

    def test_inline_image_is_replaced_by_marker_matching_its_ref(self):
        images, text = split_embedded_images(f"看圖 ![表格](data:image/webp;base64,{WEBP_B64}) 完")
        self.assertEqual(images[0].ref, "inline-1")
        self.assertNotIn("base64", text)
        self.assertIn("inline-1", text)

    def test_content_without_images_is_unchanged(self):
        images, text = split_embedded_images("純文字\n\n第二段")
        self.assertEqual(images, [])
        self.assertEqual(text, "純文字\n\n第二段")


class StripEmbeddedImagesTests(unittest.TestCase):
    """摘要用的剝除（原本放在 investment_note_repository，移到這裡共用）。"""

    def test_strip_removes_data_without_needing_valid_base64(self):
        content = "結論\n\n[image-1]: data:image/webp;base64,@@@\n"
        self.assertEqual(strip_embedded_images(content), "結論")

    def test_strip_replaces_inline_image_with_placeholder(self):
        out = strip_embedded_images(f"看圖 ![表格](data:image/webp;base64,{WEBP_B64}) 後續")
        self.assertNotIn("base64", out)
        self.assertIn("看圖", out)
        self.assertIn("後續", out)


if __name__ == "__main__":
    unittest.main()
