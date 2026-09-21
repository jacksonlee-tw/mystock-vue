"""投資筆記 AI 解析的結構化輸出定義（docs/01_Requirements/16.AI技術分析/Phase6-投資筆記 AI 解析.md）。

沿用 ai/schema.py 的教訓：LLM 不可自己排 Markdown 版面。表格改成 columns／rows 結構化欄位，
由 transcription_to_markdown() 組裝，分隔線與換行 100% 正確；段落沿用 ReportSection＋
sections_to_markdown()。所有清單欄位都給預設空值，讓模型漏填某欄時整份輸出仍可解析，
而不是整個 response.parsed 變 None。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ai.schema import ReportSection

MAX_TOPIC_TAGS = 8
MAX_TAG_LEN = 30  # investment_note_tag.name 是 VARCHAR(30)


class ExtractedSymbol(BaseModel):
    market: Literal["tw", "us"]
    symbol: str
    name: str = Field(description="模型在原文／圖中看到的公司名稱，供後端核對代號是否對得上該公司")
    evidence: str = Field(default="", description="在筆記文字或哪張圖的哪一列看到的，一句話")


class ImageTranscription(BaseModel):
    ref: str = Field(description="對應圖片標籤，例如 image-1")
    kind: Literal["table", "text"] = "text"
    title: str = ""
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    text: str = ""


class NoteExtraction(BaseModel):
    """Provider 呼叫 response_schema 時實際要求 LLM 填寫的結構。"""
    subject: str
    topic_tags: list[str] = Field(default_factory=list)
    symbols: list[ExtractedSymbol] = Field(default_factory=list)
    transcriptions: list[ImageTranscription] = Field(default_factory=list)
    summary_sections: list[ReportSection] = Field(default_factory=list)


def _cell(value: str) -> str:
    # 儲存格內的換行與直線會破壞表格結構
    return (value or "").replace("\r", " ").replace("\n", " ").replace("|", r"\|").strip()


def transcription_to_markdown(t: ImageTranscription) -> str:
    """table 且有欄位 → 組成 Markdown 表格；否則退回 text。空內容回空字串。"""
    if t.kind == "table" and t.columns:
        width = len(t.columns)
        lines = [
            "| " + " | ".join(_cell(c) for c in t.columns) + " |",
            "| " + " | ".join("---" for _ in range(width)) + " |",
        ]
        for row in t.rows:
            cells = [_cell(c) for c in row[:width]]
            cells += [""] * (width - len(cells))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)
    return (t.text or "").strip()


def normalize_topic_tags(tags: list[str]) -> list[str]:
    """去 `#` 前綴、去空白、大小寫不分去重、丟掉超過 DB 長度上限的（截斷會產生語意不明的標籤）、
    並限制總數。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        name = (raw or "").strip().lstrip("#＃").strip()
        if not name or len(name) > MAX_TAG_LEN or name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append(name)
        if len(out) >= MAX_TOPIC_TAGS:
            break
    return out
