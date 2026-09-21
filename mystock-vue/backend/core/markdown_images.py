"""筆記 Markdown 內嵌圖片（base64 data URI）的解析與剝除。

投資筆記編輯器貼上圖片時（frontend/src/utils/pastedImage.js）會把圖片內嵌進 content：
參考式定義 `[image-1]: data:image/webp;base64,...`（本文放 `![貼上圖片 1][image-1]`），
或行內 `![alt](data:image/...;base64,...)`。兩處後端邏輯都要處理它：

- 列表摘要（repositories/investment_note_repository.py）：只取前 240 字，要先剝掉 base64。
- AI 解析（note_ai/）：圖片要單獨當 image part 送給 LLM，內文則絕不可帶 base64
  （單張最大約 900KB，整段當文字送等於多送數十萬個 token）。

兩處共用同一組 regex，避免各自長歪。
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass

# 兩家 Provider（Claude／Gemini）都支援的圖片格式；其他格式（如 svg）直接略過、不送 LLM。
SUPPORTED_MIME_TYPES = ("image/webp", "image/jpeg", "image/png", "image/gif")

# 移除用的 regex 刻意放寬（不要求 base64 合法）：摘要／送 LLM 的文字都不該殘留任何 data URI。
# 行尾納入 `\r`：CRLF 內容裡 `\S+` 吃不掉 `\r`、MULTILINE 的 `$` 也不匹配 `\r` 前。
_DEFINITION_ANY_RE = re.compile(r"^[ \t]*\[[^\]\n]+\]:[ \t]*data:image/\S+[ \t\r]*$", re.MULTILINE)
_INLINE_ANY_RE = re.compile(r"!\[([^\]\n]*)\]\(data:image/[^)\s]*\)")
_BLANK_LINE_RUN_RE = re.compile(r"(?:\r?\n){3,}")

# 解析用的 regex 較嚴格：要能取出 ref／mime／base64 三段。
_DEFINITION_RE = re.compile(
    r"^[ \t]*\[(?P<ref>[^\]\n]+)\]:[ \t]*data:(?P<mime>image/[\w.+-]+);base64,(?P<data>\S+?)[ \t\r]*$",
    re.MULTILINE,
)
_INLINE_RE = re.compile(r"!\[[^\]\n]*\]\(data:(?P<mime>image/[\w.+-]+);base64,(?P<data>[^)\s]+)\)")


@dataclass(frozen=True)
class EmbeddedImage:
    ref: str  # 參考式沿用定義名稱（"image-1"）；行內圖依出現順序產生 "inline-1"
    mime_type: str
    data: bytes


def _decode(b64: str) -> bytes | None:
    try:
        return base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        return None


def extract_embedded_images(content: str) -> list[EmbeddedImage]:
    """依出現順序取出可送 LLM 的內嵌圖片：先參考式定義、再行內圖。

    不支援的 mime、base64 不合法者一律略過，不拋例外——單張壞圖不該讓整篇筆記無法解析。
    """
    images: list[EmbeddedImage] = []
    for m in _DEFINITION_RE.finditer(content):
        if m.group("mime") not in SUPPORTED_MIME_TYPES:
            continue
        data = _decode(m.group("data"))
        if data:
            images.append(EmbeddedImage(ref=m.group("ref"), mime_type=m.group("mime"), data=data))

    inline_no = 0
    for m in _INLINE_RE.finditer(content):
        inline_no += 1
        if m.group("mime") not in SUPPORTED_MIME_TYPES:
            continue
        data = _decode(m.group("data"))
        if data:
            images.append(EmbeddedImage(ref=f"inline-{inline_no}", mime_type=m.group("mime"), data=data))
    return images


def _collapse_blank_lines(text: str) -> str:
    return _BLANK_LINE_RUN_RE.sub("\n\n", text).strip()


def split_embedded_images(content: str) -> tuple[list[EmbeddedImage], str]:
    """回傳 (圖片清單, 去除 base64 後的文字)。

    文字保留 `![貼上圖片 1][image-1]` 這類參考標記（讓模型知道圖片在內文哪個位置），
    行內圖改成 `![alt](inline-N)`，ref 與 extract_embedded_images() 產生的一致。
    """
    images = extract_embedded_images(content)

    inline_no = 0

    def _inline_marker(m: re.Match) -> str:
        nonlocal inline_no
        inline_no += 1
        return f"![{m.group(1)}](inline-{inline_no})"

    text = _DEFINITION_ANY_RE.sub("", content)
    text = _INLINE_ANY_RE.sub(_inline_marker, text)
    return images, _collapse_blank_lines(text)


def strip_embedded_images(content: str) -> str:
    """列表摘要用：剝掉所有 base64，行內圖換成「圖片」佔位。"""
    text = _DEFINITION_ANY_RE.sub("", content)
    text = _INLINE_ANY_RE.sub(lambda m: f"![{m.group(1)}](圖片)", text)
    return _collapse_blank_lines(text)
