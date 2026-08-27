"""
notify/channels/__init__.py
管道自動註冊（ADR-14，比照 strategies/registry.py 的 @condition 慣例）
新增管道時：新增檔案 + 在此加一行 import
"""
from typing import Callable, Type
from .base import ChannelAdapter

# ── 全域管道登錄表 ────────────────────────────────────────────
CHANNEL_REGISTRY: dict[str, ChannelAdapter] = {}


def channel(code: str, display_name: str):
    """
    裝飾器：自動把管道類別的實例注入 CHANNEL_REGISTRY（ADR-14）

    用法：
        @channel(code="email", display_name="Email")
        class EmailChannel(ChannelAdapter):
            ...
    """
    def decorator(cls: Type[ChannelAdapter]):
        instance = cls()
        CHANNEL_REGISTRY[code] = instance
        return cls
    return decorator


def get_channel(code: str) -> ChannelAdapter | None:
    """Dispatcher 唯一取用管道的入口（§4.3，只依 channel_code 字串）"""
    return CHANNEL_REGISTRY.get(code)


# ── 觸發各管道的自我註冊 ──────────────────────────────────────
# 「新增管道 = 新增一個檔案 + 在此加一行 import」（鐵則 R2、AC-19）
from . import email_channel    # noqa: E402,F401
from . import telegram_channel # noqa: E402,F401
from . import slack_channel    # noqa: E402,F401
