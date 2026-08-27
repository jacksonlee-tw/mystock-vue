"""
ai/providers/__init__.py
Provider 自動註冊（見規格書 ADR-AI-01），比照 notify/channels/__init__.py 的 @channel 慣例。
新增 Provider 時：新增檔案（繼承 AIProvider）+ 在此加一行 import。
"""
from typing import Dict

from ai.providers.base import AIProvider

# ── 全域 Provider 登錄表 ──────────────────────────────────────
PROVIDER_REGISTRY: Dict[str, AIProvider] = {}


def ai_provider(code: str, display_name: str):
    def decorator(cls):
        instance = cls()
        instance.code = code
        instance.display_name = display_name
        PROVIDER_REGISTRY[code] = instance
        return cls
    return decorator


def get_provider(code: str) -> AIProvider | None:
    """端點唯一取用 Provider 的入口，只依 code 字串（比照 notify get_channel()）。"""
    return PROVIDER_REGISTRY.get(code)


# ── 觸發各 Provider 的自我註冊（新增 Provider＝新增檔案＋在此加一行 import）──
from ai.providers import claude_provider  # noqa: E402,F401
from ai.providers import gemini_provider  # noqa: E402,F401
