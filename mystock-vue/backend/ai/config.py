"""
ai/config.py
AI 技術分析報告設定讀取（見 docs/16.AI技術分析/AI技術分析規劃.md §9）
遵循既有 config.py／notify/config.py 慣例：load_dotenv(override=True)，改 .env 不需重啟
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

VALID_PROVIDERS = ("claude", "gemini")


def _env(key: str, default: str = "") -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() in ("true", "1", "yes")


# ── 總開關（ADR-AI-07）────────────────────────────────────────
def is_enabled() -> bool:
    return _env_bool("AI_ANALYSIS_ENABLED", False)


def get_default_provider() -> str:
    provider = _env("AI_DEFAULT_PROVIDER", "claude").lower()
    # 辨識不了的值退回 claude，設定打錯字不該讓端點整個炸掉（比照 config.get_data_source()）
    return provider if provider in VALID_PROVIDERS else "claude"


# ── Claude（Anthropic）─────────────────────────────────────────
def get_claude_api_key() -> str:
    return _env("CLAUDE_API_KEY", "")


def get_claude_model() -> str:
    return _env("CLAUDE_MODEL", "claude-sonnet-5")


# ── Gemini（Google）────────────────────────────────────────────
def get_gemini_api_key() -> str:
    return _env("GEMINI_API_KEY", "")


def get_gemini_model() -> str:
    return _env("GEMINI_MODEL", "gemini-2.5-flash")


# ── 成本與併發控管（§4.6、ADR-AI-08）───────────────────────────
def get_daily_quota() -> int:
    return _env_int("AI_DAILY_QUOTA", 20)


def get_stuck_timeout_min() -> int:
    return _env_int("AI_STUCK_TIMEOUT_MIN", 10)


def get_request_timeout_sec() -> int:
    return _env_int("AI_REQUEST_TIMEOUT_SEC", 90)


def get_max_output_tokens() -> int:
    return _env_int("AI_MAX_OUTPUT_TOKENS", 8000)


def get_max_image_mb() -> int:
    return _env_int("AI_MAX_IMAGE_MB", 4)


def allow_force_regenerate() -> bool:
    """開發除錯用逃生門，正式環境務必保持 false（§4.6）。"""
    return _env_bool("AI_ALLOW_FORCE_REGENERATE", False)


# ── 紀錄保留（§5.10）───────────────────────────────────────────
def get_report_retention_days() -> int:
    return _env_int("AI_REPORT_RETENTION_DAYS", 365)


def get_execution_retention_days() -> int:
    return _env_int("AI_EXECUTION_RETENTION_DAYS", 730)


def get_activity_log_retention_days() -> int:
    return _env_int("AI_ACTIVITY_LOG_RETENTION_DAYS", 365)


# ── 提示詞版本（§5.5）───────────────────────────────────────────
def get_prompt_version() -> str:
    # v4：Phase1-基礎量化與技術面 FR-P1-9，System Prompt 新增第 6 點（MACD／RSI／布林／ATR）。
    return _env("AI_PROMPT_VERSION", "v4")


# ── 可選模型清單（§4.3 附加、v3.4 新增）────────────────────────
# 使用者在產生報告前可從此清單挑模型（見 GET /api/v1/ai/models）。刻意用程式碼維護一份
# 白名單，而不是讓前端傳任意字串直接打 Provider API：① 避免打錯字浪費一次呼叫才知道；
# ② 排除圖片生成／即時語音／翻譯／TTS 等本模組用不到的變體（使用者需求明確排除 image 系列）。
# 新模型上市時在這裡加一筆即可，不需要改任何呼叫邏輯。
CLAUDE_SELECTABLE_MODELS: list[dict[str, str]] = [
    {"id": "claude-opus-5", "label": "Claude Opus 5", "tier": "旗艦"},
    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5", "tier": "平衡（預設）"},
    {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "tier": "輕量"},
]

# 確認於 https://ai.google.dev/gemini-api/docs/models（2026-08-28）。
# 實測驗證狀態（見規格書 v3.4）：
#   - gemini-2.5-flash：已用真實 API 多次成功呼叫，確認可用（唯一實測過的機型）。
#   - gemini-2.5-flash-lite：實測直接回 404「no longer available to new users」，
#     官方訊息指定改用 gemini-3.5-flash-lite——因此**不放進**這份清單，避免使用者選了就壞。
#   - 其餘機型（3.1 Pro／3.6 Flash／3.5 Flash／3.5 Flash-Lite／3-flash-preview／
#     3.1 Flash-Lite／2.5 Pro）皆未實測，僅依官方模型頁與定價頁核對過名稱與定價存在，
#     不保證這個 API 金鑰／地區實際打得通；gemini-3-flash-preview 連定價都查無資料。
# gemini-3.6-flash：定價頁已收錄，但使用者實際看到的模型清單頁面當下尚未列出，可能是新機型
# 正在分區／分帳號推送中；若呼叫時回 404，屬於 Google 端尚未對此帳號開通，非本專案程式問題。
GEMINI_SELECTABLE_MODELS: list[dict[str, str]] = [
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro", "tier": "旗艦（進階推論）"},
    {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "tier": "旗艦（速度與智慧平衡）"},
    {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash", "tier": "高智慧多模態"},
    {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash (Preview)", "tier": "預覽版"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "tier": "低成本輕量"},
    {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite", "tier": "低成本輕量（舊版）"},
    {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "tier": "旗艦（推論與編程）"},
    {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tier": "平衡成本效益（預設，已實測）"},
]

SELECTABLE_MODELS: dict[str, list[dict[str, str]]] = {
    "claude": CLAUDE_SELECTABLE_MODELS,
    "gemini": GEMINI_SELECTABLE_MODELS,
}


def get_selectable_models(provider: str) -> list[dict[str, str]]:
    return SELECTABLE_MODELS.get(provider, [])


def is_valid_model(provider: str, model: str) -> bool:
    return any(m["id"] == model for m in SELECTABLE_MODELS.get(provider, []))


# ── 模型定價（§10.4，USD / 1M tokens，皆為標準付費層 text/image 輸入單價）─────
# 找不到的模型回傳 None，estimated_cost_usd 不可用猜測值填（§10.4）。
# Gemini 價目確認於 https://ai.google.dev/gemini-api/docs/pricing（2026-08-28）。
# gemini-3.6-flash 為限時優惠價（至 2026-12-31），2027-01-01 起漲為 input $1.50／output $7.50。
MODEL_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3.6-flash": {"input": 0.75, "output": 3.75},
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    # gemini-2.5-flash-lite 已從 GEMINI_SELECTABLE_MODELS 移除（新用戶 404），保留定價僅供
    # 舊資料回溯查閱歷史報告的 estimated_cost_usd 計算基準，不影響新請求（不在白名單內）。
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
}


def get_model_pricing(model: str) -> dict[str, float] | None:
    return MODEL_PRICING_USD_PER_MTOK.get(model)
