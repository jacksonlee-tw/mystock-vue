"""
ai/errors.py
AI 技術分析報告模組的型別化例外（見規格書 §4.7）。
Provider 層不得讓 SDK 原生例外穿透到端點，一律轉為此處的型別；
端點以既有封套 {"success": false, "error": {...}} 回應，例外處理器註冊於 main.py，
比照既有 SymbolNotFoundException／NotifyUnauthorizedException 的作法。
"""


class AIDisabledException(Exception):
    """AI_ANALYSIS_ENABLED=false 時（403 AI_DISABLED）。"""
    pass


class AIStorageUnavailableException(Exception):
    """資料庫不可用（503 AI_STORAGE_UNAVAILABLE）。"""
    pass


class AIQuotaExceededException(Exception):
    """今日新報告數已達 AI_DAILY_QUOTA（429 AI_QUOTA_EXCEEDED）。"""
    pass


class AIAnalysisInProgressException(Exception):
    """佔位失敗、他人正在執行且未逾時（409 AI_ANALYSIS_IN_PROGRESS）。"""
    pass


class AIProviderMisconfiguredException(Exception):
    """金鑰未設定或驗證失敗（500 AI_PROVIDER_MISCONFIGURED）。不得攜帶金鑰片段。"""
    pass


class AIInvalidRequestException(Exception):
    """請求參數不合法，例如不支援的 provider 代碼（400 AI_INVALID_REQUEST）。"""
    pass


class AIImageTooLargeException(Exception):
    """送出的 K 線圖超過 AI_MAX_IMAGE_MB（400 AI_IMAGE_TOO_LARGE，見規格書 §4.1）。"""
    pass


class AIRateLimitedException(Exception):
    """Provider 限流（429 AI_RATE_LIMITED）。"""

    def __init__(self, message: str = "", retry_after_sec: int | None = None):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class AITimeoutException(Exception):
    """呼叫逾時（504 AI_TIMEOUT）。"""
    pass


class AIProviderUnreachableException(Exception):
    """連線失敗（502 AI_PROVIDER_UNREACHABLE）。"""
    pass


class AIProviderError(Exception):
    """未歸類的 Provider 例外，保底轉換用。"""
    pass
