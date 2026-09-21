import base64
import unittest

from ai.providers import get_provider
from ai.providers.base import AIProvider
from ai.providers.claude_provider import build_multimodal_content
from ai.providers.gemini_provider import build_multimodal_contents
from core.markdown_images import EmbeddedImage

WEBP = EmbeddedImage(ref="image-1", mime_type="image/webp", data=b"RIFF-webp")
JPEG = EmbeddedImage(ref="image-2", mime_type="image/jpeg", data=b"\xff\xd8-jpeg")


class ClaudeContentBlocksTests(unittest.TestCase):
    def test_each_image_is_labelled_then_sent_with_its_own_media_type(self):
        blocks = build_multimodal_content([WEBP, JPEG], "請分析")
        self.assertEqual([b["type"] for b in blocks], ["text", "image", "text", "image", "text"])
        self.assertIn("image-1", blocks[0]["text"])
        self.assertEqual(blocks[1]["source"]["media_type"], "image/webp")
        self.assertEqual(base64.b64decode(blocks[1]["source"]["data"]), b"RIFF-webp")
        self.assertIn("image-2", blocks[2]["text"])
        self.assertEqual(blocks[3]["source"]["media_type"], "image/jpeg")
        self.assertEqual(blocks[-1], {"type": "text", "text": "請分析"})

    def test_media_type_is_never_hardcoded_to_png(self):
        # analyze() 把 media_type 寫死 image/png；貼上的圖是 WebP，沿用會被 API 拒絕或誤判
        blocks = build_multimodal_content([WEBP], "x")
        self.assertNotIn("image/png", [b.get("source", {}).get("media_type") for b in blocks])

    def test_no_images_is_just_the_prompt(self):
        self.assertEqual(build_multimodal_content([], "純文字"), [{"type": "text", "text": "純文字"}])


class GeminiContentsTests(unittest.TestCase):
    def test_each_image_is_labelled_then_sent_with_its_own_mime_type(self):
        contents = build_multimodal_contents([WEBP, JPEG], "請分析")
        self.assertEqual(len(contents), 5)
        self.assertIn("image-1", contents[0])
        self.assertEqual(contents[1].inline_data.mime_type, "image/webp")
        self.assertEqual(contents[1].inline_data.data, b"RIFF-webp")
        self.assertIn("image-2", contents[2])
        self.assertEqual(contents[3].inline_data.mime_type, "image/jpeg")
        self.assertEqual(contents[-1], "請分析")

    def test_no_images_is_just_the_prompt(self):
        self.assertEqual(build_multimodal_contents([], "純文字"), ["純文字"])


class BaseContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_raises_not_implemented_so_existing_providers_stay_untouched(self):
        class Bare(AIProvider):
            code = "bare"
            display_name = "Bare"

            async def analyze(self, image_base64, system_prompt, user_prompt, model=None):
                raise AssertionError("不該被呼叫")

        with self.assertRaises(NotImplementedError):
            await Bare().extract_structured_multimodal("s", "u", dict, images=[])

    async def test_both_real_providers_implement_it(self):
        for code in ("claude", "gemini"):
            method = type(get_provider(code)).extract_structured_multimodal
            self.assertIsNot(method, AIProvider.extract_structured_multimodal, code)


if __name__ == "__main__":
    unittest.main()
