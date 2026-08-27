"""
ai/schema.py
AI 技術分析報告的結構化輸出定義（見規格書 §4.5，ADR-AI-06）。

v3.3 修訂：report_markdown 不再要求 LLM 直接產生一整段自由文字 Markdown（含「### 標題」）。
實測發現 Claude／Gemini 都會不穩定地把「### 標題」跟前一句話黏在同一行（例如
「...動能延續。### 籌碼面分析三大法人近五日...」），導致標題無法被正確解析——這是自由文字裡的
排版慣例，結構化輸出的 JSON Schema 只保證「欄位互不相混」，保證不了「一個字串裡的換行規則」。
改成請 LLM 把每個段落拆成 {title, body} 的結構化陣列（LLMAnalysisReport.sections），
Markdown 的標題與段落間距改由我們自己的 sections_to_markdown() 組裝，100% 保證正確斷行，
不再賭模型會不會乖乖照排版規則輸出。
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PriceLevel(BaseModel):
    price: float
    label: str


class ReportSection(BaseModel):
    """一個報告段落。title 只填精簡的章節標題（不含「### 」前綴、不加粗），
    body 為該段落的完整說明文字（可用 **粗體** 標關鍵數字，但不得在 body 裡再重複章節標題）。"""
    title: str
    body: str


class LLMAnalysisReport(BaseModel):
    """Provider 呼叫 output_format／response_schema 時實際要求 LLM 填寫的結構。
    不直接對外／不進資料庫——見 AnalysisReport（by from_llm_report() 轉換）。"""
    verdict: Literal["bullish", "bearish", "neutral"]
    headline: str
    support_levels: list[PriceLevel] = Field(default_factory=list)
    resistance_levels: list[PriceLevel] = Field(default_factory=list)
    stop_loss: Optional[float] = None
    sections: list[ReportSection] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class AnalysisReport(BaseModel):
    """對外契約：API 回應與 ai_analysis_report.report_markdown 欄位維持完整字串，
    不因這次的結構化改動而變動任何下游（端點／前端／資料表）。"""
    verdict: Literal["bullish", "bearish", "neutral"]
    headline: str
    support_levels: list[PriceLevel] = Field(default_factory=list)
    resistance_levels: list[PriceLevel] = Field(default_factory=list)
    stop_loss: Optional[float] = None
    report_markdown: str
    confidence: Literal["high", "medium", "low"]


def sections_to_markdown(sections: list[ReportSection]) -> str:
    """由結構化段落組裝完整 Markdown，標題與內文間的空行由字串組裝保證，不依賴模型自律。"""
    parts = []
    for sec in sections:
        title = (sec.title or "").strip()
        body = (sec.body or "").strip()
        if not body:
            continue
        parts.append(f"### {title}\n\n{body}" if title else body)
    return "\n\n".join(parts)


def from_llm_report(llm_report: LLMAnalysisReport) -> AnalysisReport:
    return AnalysisReport(
        verdict=llm_report.verdict,
        headline=llm_report.headline,
        support_levels=llm_report.support_levels,
        resistance_levels=llm_report.resistance_levels,
        stop_loss=llm_report.stop_loss,
        report_markdown=sections_to_markdown(llm_report.sections),
        confidence=llm_report.confidence,
    )
