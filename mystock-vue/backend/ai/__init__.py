"""
ai/__init__.py
AI 技術分析報告模組（見 docs/16.AI技術分析/AI技術分析規劃.md）。
匯入本套件即觸發 ai.providers 的 Provider 自我註冊（ADR-AI-01）。
"""
from ai import providers  # noqa: F401 — 觸發 PROVIDER_REGISTRY 註冊
