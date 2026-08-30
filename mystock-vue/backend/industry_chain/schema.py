"""
industry_chain/schema.py
LLM 知識萃取的結構化輸出定義（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §4.7.2）。

比照 ai/schema.py 的既有慣例：Pydantic `BaseModel`，作為 Provider 呼叫
`response_schema`／`output_format` 時實際要求 LLM 填寫的結構。`chain_id` 由我們自己送出的值
為準，模型回傳值只用來核對是否一致（見 extractor.py），不讓模型有機會創造新的 chain_id。
"""
from typing import Literal

from pydantic import BaseModel, Field


class ChainEdgeItem(BaseModel):
    """一筆模型萃取出的上下游關聯。`upstream_name`／`downstream_name` 與代號並存是最有效的
    低成本幻覺偵測（見 §4.7.2「要求 name 與 symbol 並存」的設計理由）：LLM 最典型的錯誤不是
    掰出不存在的公司，而是公司對但代號記錯，validator.py 的校驗二專門攔這個。"""
    upstream_symbol: str
    upstream_name: str
    downstream_symbol: str
    downstream_name: str
    relation_tier: int = Field(..., ge=1, le=2, description="關聯層級（1 代表一階直供，2 代表二階間接）")
    component_type: str
    confidence: Literal["high", "medium", "low"]
    evidence: str = ""


class ChainExtractionResult(BaseModel):
    """Provider 呼叫 response_schema／output_format 時實際要求 LLM 填寫的結構。"""
    chain_id: str
    edges: list[ChainEdgeItem] = Field(default_factory=list)
    notes: str = ""
