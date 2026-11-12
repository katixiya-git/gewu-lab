"""全局异常处理：把各类异常统一包成 Result 信封。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.result import Result

logger = logging.getLogger(__name__)

_HTTP_MESSAGES = {
    404: "请求的资源不存在",
    405: "请求方法不允许",
}


def _body(code: int, message: str, data=None) -> dict:
    return Result.fail(code=code, message=message, data=data).model_dump(mode="json")


def _format_validation_error(error: dict) -> str:
    """把 Pydantic 的英文报错翻成前端可直接展示的中文。"""
    location = [str(item) for item in error.get("loc", []) if item not in ("body", "query", "path")]
    field = ".".join(location)
    error_type = error.get("type", "")
    ctx = error.get("ctx") or {}

    if error_type == "missing":
        reason = "不能为空"
    elif error_type == "string_too_short":
        reason = f"长度不能少于 {ctx.get('min_length', '?')} 个字符"
    elif error_type == "string_too_long":
        reason = f"长度不能超过 {ctx.get('max_length', '?')} 个字符"
    elif error_type == "string_type":
        reason = "必须是字符串"
    elif error_type == "int_parsing":
        reason = "必须是整数"
    elif error_type == "value_error":
        reason = "取值不合法"
    else:
        reason = error.get("msg", "参数不合法")

    return f"{field}: {reason}" if field else reason


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """业务里主动 raise 的 HTTPException（401/403/404 等）。"""
        default_detail = exc.detail in (None, "", "Not Found", "Method Not Allowed")
        if default_detail:
            detail = _HTTP_MESSAGES.get(exc.status_code, "请求失败")
        elif isinstance(exc.detail, str):
            detail = exc.detail
        else:
            detail = "请求失败"
        return JSONResponse(status_code=exc.status_code, content=_body(exc.status_code, detail))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """入参校验失败：提取第一条错误，拼成「字段: 原因」。"""
        errors = exc.errors()
        message = _format_validation_error(errors[0]) if errors else "参数不合法"
        return JSONResponse(status_code=422, content=_body(422, message, data=errors))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期异常记日志，对外只暴露通用提示。"""
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_body(500, "服务器内部错误，请稍后重试"))
