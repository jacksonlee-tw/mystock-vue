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
    return _env("GEMINI_MODEL", "gemini-3.6-flash")


# ── 成本與併發控管（§4.6、ADR-AI-08）───────────────────────────
def get_daily_quota() -> int:
    return _env_int("AI_DAILY_QUOTA", 20)


def get_stuck_timeout_min() -> int:
    return _env_int("AI_STUCK_TIMEOUT_MIN", 10)


def get_request_timeout_sec() -> int:
    return _env_int("AI_REQUEST_TIMEOUT_SEC", 90)


def get_max_output_tokens() -> int:
    return _env_int("AI_MAX_OUTPUT_TOKENS", 8000)


def get_extraction_max_output_tokens() -> int:
    """`extract_structured()`（ADR-IC-12）專用輸出上限，預設高於一般 AI_MAX_OUTPUT_TOKENS——
    Gemini 2.5+ 思考模型的推理與最終 JSON 共用同一份輸出配額，配額太小時會被思考耗盡，
    連 JSON 都生不出來（finish_reason=MAX_TOKENS 且 response.parsed 為 None）。"""
    return _env_int("AI_EXTRACTION_MAX_OUTPUT_TOKENS", 16000)


def get_max_image_mb() -> int:
    return _env_int("AI_MAX_IMAGE_MB", 4)


def allow_force_regenerate() -> bool:
    """開發除錯用逃生門，正式環境務必保持 false（§4.6）。"""
    return _env_bool("AI_ALLOW_FORCE_REGENERATE", False)


# ── Phase 5：監控清單批次產生（docs/16.AI技術分析/Phase5-三層式 AI 決策引擎與戰情室.md
#    §8／FR-5.3）── 批次與手動配額各自獨立計算，互不排擠（Q3 決議）；批次獨立開關（Q4／§4.2），
#    未開啟時排程完全不觸發、不計費，與 AI_ANALYSIS_ENABLED 分層（後者是全站總開關）。
def get_batch_enabled() -> bool:
    return _env_bool("AI_BATCH_ENABLED", False)


def get_batch_daily_quota() -> int:
    return _env_int("AI_BATCH_DAILY_QUOTA", 70)


def get_batch_exclude_etf() -> bool:
    """Q2 決議：預設排除 ETF／ETN／TDR／特別股／受益證券（比照規則引擎既有 ADR-SP-13），
    三層式分析對這些證券退化最嚴重且籌碼語意不同；使用者仍可在個股頁手動點擊產生。"""
    return _env_bool("AI_BATCH_EXCLUDE_ETF", True)


def get_batch_provider() -> str:
    """未設定 AI_BATCH_PROVIDER 時跟隨 get_default_provider()（手動點擊的預設 Provider）——
    使用者部署時往往只設定一組金鑰，批次若寫死另一個 Provider，沒設金鑰時會整輪失敗，
    設了金鑰也會因為 provider+model 跟手動不同而各自佔一份每日唯一鍵、無法互相回讀快取
    （AC-P5-10 的精神：同一標的當天已有報告就不該再算一次）。仍可在 .env 明確覆寫成不同
    Provider（例如金鑰充裕、想讓批次固定用某個較穩定的模型）。"""
    provider = _env("AI_BATCH_PROVIDER", "").lower()
    if provider in VALID_PROVIDERS:
        return provider
    return get_default_provider()


def get_batch_model() -> str:
    """未設定 AI_BATCH_MODEL 時跟隨批次實際採用的 Provider 之 .env 預設模型（同一條理由見
    get_batch_provider()）——不得寫死成固定 Provider 的模型 ID，否則跟隨 get_batch_provider()
    切換後兩者會對不上（例如 provider 已改成 gemini，model 卻仍是 claude-sonnet-5）。"""
    model = _env("AI_BATCH_MODEL", "")
    if model:
        return model
    return _default_model_for_provider(get_batch_provider())


def _default_model_for_provider(provider: str) -> str:
    if provider == "claude":
        return get_claude_model()
    if provider == "gemini":
        return get_gemini_model()
    return provider


def set_batch_settings(
    *,
    enabled: bool | None = None,
    daily_quota: int | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """寫回 .env（比照 config.py::save_schedule_config() 的既有慣例，同一份 .env、同一支
    _set_env_values() 寫入邏輯，就地覆寫或附加，只讀寫檔案一次）。存檔後 get_batch_enabled()／
    get_batch_daily_quota() 下次讀取即生效（load_dotenv(override=True)），不需重啟服務——
    這是 UI「批次設定」開關能即時生效的唯一原因。

    provider／model 一起寫回：只給其中一個時，用另一個目前生效的值／該 Provider 的預設模型
    補齊後兩者一起寫——get_batch_model() 只是原樣讀出 AI_BATCH_MODEL、不會反查是否配對得上
    AI_BATCH_PROVIDER，若只改 Provider 沒同時更新 Model，會留下上一個 Provider 的模型 ID，
    下次呼叫時 provider/model 對不上（例如 provider 已是 gemini，model 卻仍是
    claude-sonnet-5）。"""
    from config import _set_env_values

    pairs: dict[str, str] = {}
    if enabled is not None:
        pairs["AI_BATCH_ENABLED"] = "true" if enabled else "false"
    if daily_quota is not None:
        if daily_quota < 1:
            raise ValueError("AI_BATCH_DAILY_QUOTA 必須 >= 1")
        pairs["AI_BATCH_DAILY_QUOTA"] = str(daily_quota)
    if provider is not None or model is not None:
        effective_provider = provider or get_batch_provider()
        if effective_provider not in VALID_PROVIDERS:
            raise ValueError(f"不支援的 Provider：{effective_provider}")
        effective_model = model or _default_model_for_provider(effective_provider)
        if not is_valid_model(effective_provider, effective_model):
            raise ValueError(f"{effective_provider} 不支援的模型：{effective_model}")
        pairs["AI_BATCH_PROVIDER"] = effective_provider
        pairs["AI_BATCH_MODEL"] = effective_model
    if pairs:
        _set_env_values(pairs)


# ── 近期策略訊號佐證（Phase2-籌碼面與基本面量化擴充 設計文件 FR-4，比照 ADR-AI-12：可調參數走
#    .env，不寫死）──────────────────────────────────────────────
def get_recent_alerts_lookback_days() -> int:
    return _env_int("AI_RECENT_ALERTS_DAYS", 10)


def get_recent_alerts_limit() -> int:
    return _env_int("AI_RECENT_ALERTS_LIMIT", 5)


# ── 紀錄保留（§5.10）───────────────────────────────────────────
def get_report_retention_days() -> int:
    return _env_int("AI_REPORT_RETENTION_DAYS", 365)


def get_execution_retention_days() -> int:
    return _env_int("AI_EXECUTION_RETENTION_DAYS", 730)


def get_activity_log_retention_days() -> int:
    return _env_int("AI_ACTIVITY_LOG_RETENTION_DAYS", 365)


# ── 產業鏈知識圖譜 LLM 萃取成本閘門（見 docs/16.AI技術分析/
#    Phase3-產業鏈知識圖譜與輪動模型.md §4.7.5、ADR-IC-13）─────────────
# 放在這裡而非 industry_chain/config.py：這是「LLM 呼叫」的成本閘門參數，ai/config.py
# 已是全站 LLM 相關設定的既有集中點；industry_chain/config.py 保留給「產業鏈骨架 YAML／
# 功能旗標」。AI_DAILY_QUOTA 數不到本模組的呼叫（該閘門只數 ai_analysis_report），這是
# 本模組唯一的花費天花板，需求量遠小於一般診股報告，預設 20 已遠大於 3 條鏈的正常用量。
def get_industry_chain_monthly_call_cap() -> int:
    return _env_int("IC_LLM_MONTHLY_CALL_CAP", 20)


# ── 投資筆記 AI 解析（docs/01_Requirements/16.AI技術分析/Phase6-投資筆記 AI 解析.md）──────
# 獨立開關與配額：筆記解析是「一篇一次含圖呼叫」，成本結構與診股報告不同，不與 AI_DAILY_QUOTA
# 共用計數（該閘門只數 ai_analysis_report，數不到本功能的呼叫）。仍須先通過全站總開關
# AI_ANALYSIS_ENABLED，本開關預設關閉，開啟前不會產生任何費用。
def get_note_ai_enabled() -> bool:
    return _env_bool("NOTE_AI_ENABLED", False)


def get_note_ai_daily_quota() -> int:
    return _env_int("NOTE_AI_DAILY_QUOTA", 20)


def get_note_ai_max_images() -> int:
    """單次解析最多送幾張圖給 LLM（成本上限）；超過的圖略過並在回應中告知。"""
    return max(0, _env_int("NOTE_AI_MAX_IMAGES", 4))


# ── 提示詞版本（§5.5）───────────────────────────────────────────
def get_prompt_version() -> str:
    # v4：Phase1-基礎量化與技術面 FR-P1-9，System Prompt 新增第 6 點（MACD／RSI／布林／ATR）。
    # v5：Phase2-籌碼面與基本面量化擴充 FR-4，System Prompt 新增第 7、8 點（基本面與估值檢核、
    #     市場資金定位）＋輸出規範新增一條近期策略訊號僅供佐證的限制。對外結構化輸出七個欄位不變
    #     （ADR-P2-05），僅供 metadata 追溯用。
    # v6：Phase5-三層式 AI 決策引擎與戰情室 FR-5.1／FR-5.2，System Prompt 第 7 點新增「最近一季
    #     EPS 年增率」、輸出規範新增 target_price 一條，User Prompt 新增 EPS 區塊。批次走
    #     BATCH_SYSTEM_PROMPT（同版號、純數值版），可由 ai_llm_execution.request_meta.mode
    #     ＝"batch_text_only" 與 ai_analysis_report.trigger_type 區分。
    return _env("AI_PROMPT_VERSION", "v6")


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
# 預設模型（2026-09-01 起）：使用者要求改為 gemini-3.6-flash（見 get_gemini_model()／
# .env.example 的 GEMINI_MODEL）——速度與智慧平衡，優惠價至 2026-12-31（見下方定價表註記）；
# 未實測，若此帳號尚未開通而回 404，可暫時於 .env 把 GEMINI_MODEL 改回 gemini-2.5-flash。
GEMINI_SELECTABLE_MODELS: list[dict[str, str]] = [
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro", "tier": "旗艦（進階推論）"},
    {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "tier": "旗艦（速度與智慧平衡，預設）"},
    {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash", "tier": "高智慧多模態"},
    {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash (Preview)", "tier": "預覽版"},
    {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "tier": "低成本輕量"},
    {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite", "tier": "低成本輕量（舊版）"},
    {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "tier": "旗艦（推論與編程）"},
    {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tier": "平衡成本效益（已實測）"},
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
