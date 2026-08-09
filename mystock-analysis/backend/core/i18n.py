"""多國語系支援模組（i18n）

提供：
  - translate(key, locale, **kwargs)  — 依語系鍵值翻譯並格式化訊息
  - get_locale(Accept-Language)       — FastAPI Depends 依存，從 Request Header 解析語系
  - DEFAULT_LOCALE                    — 系統預設語系（zh-TW）

支援語系：zh-TW（繁體中文）、zh-CN（簡體中文）
語系定義檔位置：{project_root}/locales/<locale>.json
"""
import json
import logging
import os
from functools import lru_cache

from fastapi import Header

log = logging.getLogger(__name__)

DEFAULT_LOCALE = "zh-TW"
SUPPORTED_LOCALES = ("zh-TW", "zh-CN")

# ── locales/ 目錄路徑（相對於 main.py 所在目錄）──────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LOCALES_DIR = os.path.join(_BASE_DIR, "locales")


@lru_cache(maxsize=None)
def _load_locale(locale: str) -> dict:
    """載入並快取指定語系的 JSON 翻譯字典。"""
    path = os.path.join(_LOCALES_DIR, f"{locale}.json")
    if not os.path.isfile(path):
        log.warning("i18n: 語系檔案不存在，略過 %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def translate(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    """依語系鍵值取得翻譯文字，並以 kwargs 進行格式化替換。

    找不到 key 時依序 fallback：locale → DEFAULT_LOCALE → 回傳 key 本身。

    Args:
        key:    語系鍵值，對應 locales/*.json 的 key（例如 "TICKET_NOT_FOUND"）。
        locale: 目標語系代碼，預設 "zh-TW"。
        **kwargs: 格式化參數（例如 ticket_no="2603140001"）。

    Returns:
        翻譯且格式化後的字串；查無 key 時回傳 key 本身。
    """
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE

    translations = _load_locale(locale)
    text = translations.get(key)

    # fallback 至預設語系
    if text is None and locale != DEFAULT_LOCALE:
        text = _load_locale(DEFAULT_LOCALE).get(key)

    # 最終 fallback：回傳 key 本身（方便開發時快速定位未翻譯的 key）
    if text is None:
        log.warning("i18n: 缺少語系 key='%s' locale='%s'", key, locale)
        return key

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError) as exc:
            log.warning("i18n: 格式化失敗 key='%s' kwargs=%s err=%s", key, kwargs, exc)
            return text

    return text


def get_locale(
    accept_language: str = Header(default=DEFAULT_LOCALE, alias="Accept-Language"),
) -> str:
    """FastAPI Depends 依存：從 Accept-Language Header 解析目標語系。

    支援的語系代碼（不區分大小寫）：
        zh-TW, zh-Hant, zh-Hant-TW  → "zh-TW"（繁體中文，預設）
        zh-CN, zh-Hans, zh-Hans-CN  → "zh-CN"（簡體中文）

    無法辨識時預設回傳 "zh-TW"。

    Usage:
        @router.post("/example")
        async def example(locale: str = Depends(get_locale)):
            ...
    """
    # 取第一個語系偏好（e.g. "zh-CN,zh;q=0.9" → "zh-CN"）
    first = accept_language.split(",")[0].strip().split(";")[0].strip()
    if first.lower() in ("zh-cn", "zh-hans", "zh-hans-cn"):
        return "zh-CN"
    return "zh-TW"
