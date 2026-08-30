"""
industry_chain/errors.py
產業鏈知識圖譜模組的型別化例外（見 docs/16.AI技術分析/Phase3-產業鏈知識圖譜與輪動模型.md §7）。

比照 ai/errors.py 的既有慣例：內部模組不得讓例外原始型別穿透到端點，一律轉為此處的型別；
端點以既有封套 {"success": false, "error": {...}} 回應，例外處理器註冊於 main.py。
"""


class IndustryChainDisabledException(Exception):
    """INDUSTRY_CHAIN_ENABLED=false 時（403 IC_DISABLED）。"""
    pass


class IndustryChainStorageUnavailableException(Exception):
    """資料庫不可用（503 IC_STORAGE_UNAVAILABLE）。"""
    pass


class IndustryChainNotFoundException(Exception):
    """查無此 chain_id（404 IC_CHAIN_NOT_FOUND）。"""
    pass


class IndustryChainCrawlInProgressException(Exception):
    """同一時間已有萃取工作在跑（409 IC_CRAWL_IN_PROGRESS）。"""
    pass


class IndustryChainCapExceededException(Exception):
    """本月 LLM 萃取呼叫已達 IC_LLM_MONTHLY_CALL_CAP（429 IC_LLM_CAP_HIT）。"""
    pass


class IndustryChainModelInvalidException(Exception):
    """模型不在 ai/config.py 的白名單內（400 IC_LLM_MODEL_INVALID）。"""
    pass


class IndustryChainNoKeyException(Exception):
    """對應 Provider 的 API 金鑰未設定（500 IC_LLM_NO_KEY）。"""
    pass


class IndustryChainConfigInvalidException(Exception):
    """維護對話框存檔時，骨架設定未通過驗證（400 IC_CONFIG_INVALID）。"""
    pass
