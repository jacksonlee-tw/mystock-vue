"""全域例外處理器（Global Exception Handlers）

遵循 tcci-fastapi-enterprise-architecture 規範：
- 攔截 AppException，透過 i18n translate() 翻譯錯誤訊息
- 統一回傳格式：{"success": false, "error_code": "...", "message": "..."}
- 攔截未預期的 Exception，回傳 500 通用錯誤（不洩漏內部細節）

register(app) 需在 main.py 中呼叫，於路由掛載前完成。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import AppException
from backend.core.i18n import DEFAULT_LOCALE, translate

log = logging.getLogger(__name__)


def _extract_locale(request: Request) -> str:
    """從 Request Header 解析語系（處理器中無法使用 Depends，手動解析）。"""
    header = request.headers.get("Accept-Language", DEFAULT_LOCALE)
    first = header.split(",")[0].strip().split(";")[0].strip()
    if first.lower() in ("zh-cn", "zh-hans", "zh-hans-cn"):
        return "zh-CN"
    return "zh-TW"


async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    """將 AppException 攔截並翻譯為標準 JSON 錯誤回應。

    回應格式：
        HTTP {exc.status_code}
        { "success": false, "error_code": "...", "message": "翻譯後文字" }
    """
    locale = _extract_locale(request)
    message = translate(exc.error_code, locale, **exc.kwargs)
    log.warning(
        "AppException: error_code=%s status=%s locale=%s message=%s",
        exc.error_code, exc.status_code, locale, message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error_code": exc.error_code, "message": message},
    )


async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """攔截所有未預期例外，回傳 500，不洩漏 stack trace。"""
    log.exception("未預期例外：%s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error_code": "INTERNAL_ERROR", "message": "伺服器發生內部錯誤"},
    )


def register(app: FastAPI) -> None:
    """將全域例外處理器掛載至 FastAPI 應用程式。

    應在 main.py 中呼叫，置於所有路由掛載之前。

    Usage:
        from backend.core import handlers
        handlers.register(app)
    """
    app.add_exception_handler(AppException, _handle_app_exception)
