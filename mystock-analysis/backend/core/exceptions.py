"""自定義例外類別（Application Exceptions）

遵循 tcci-fastapi-enterprise-architecture 規範：
- Service / CRUD 層只拋出 AppException，傳遞 error_code，絕不寫死語言文字。
- Router 層或 handlers.py 負責將 error_code 透過 i18n 翻譯為使用者語言文字。
- 繼承 starlette HTTPException 確保在所有 FastAPI/Starlette 版本中可被正確攔截。
"""
from starlette.exceptions import HTTPException


class AppException(HTTPException):
    """過磅系統統一應用程式例外。

    所有業務邏輯錯誤均應透過此例外拋出，而非直接使用
    fastapi.HTTPException 或在 Service 層寫死錯誤文字。

    Attributes:
        error_code:  語系鍵值（對應 locales/*.json 中的 key），例如 "TICKET_NOT_FOUND"。
        status_code: HTTP 狀態碼，預設 400。
        kwargs:      傳遞給 translate() 的格式化參數（例如 ticket_no="1234"）。
    """

    def __init__(self, error_code: str, status_code: int = 400, **kwargs):
        self.error_code = error_code
        self.kwargs = kwargs
        super().__init__(status_code=status_code, detail=error_code)
