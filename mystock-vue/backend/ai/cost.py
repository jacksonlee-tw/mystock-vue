"""
ai/cost.py
LLM 呼叫的成本估算（見規格書 §10.4）。抽成獨立模組供 api/v1/endpoints/ai_analysis.py（手動診股）
與 ai/batch_job.py（Phase5 監控清單批次）共用，避免兩條路徑各自維護一份定價換算邏輯。
"""
from __future__ import annotations

from ai import config as ai_config


def estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    pricing = ai_config.get_model_pricing(model)
    if not pricing or input_tokens is None or output_tokens is None:
        return None
    return round(input_tokens / 1_000_000 * pricing["input"] + output_tokens / 1_000_000 * pricing["output"], 6)
