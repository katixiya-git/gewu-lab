"""全局异常处理：把所有异常统一包成 Result 信封。

FastAPI 默认的 404/422 是英文纯文本，前端拆不动；这里注册三类处理器，
保证无论成功失败，响应体都是 ``{code, message, data}``。
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.result import Result

logger = logging.getLogger(__name__)

# 框架自带的英文 detail 不直接给前端，换成中文
_HTTP_MESSAGES = {
    404: "请求的资源不存在",
    405: "请求方法不允许",
}


def _body(code: int, message: str, data=None) -> dict:
    """把信封序列化成可直接塞进 JSONResponse 的 dict。"""
    return Result.fail(code=code, message=message, data=data).model_dump(mode="json")


def _format_validation_error(error: dict) -> str:
    """把 Pydantic 的英文报错翻成前端可直接展示的中文。

    Args:
        error: ``RequestValidationError.errors()`` 里的一条记录。

    Returns:
        str: 形如「password: 长度不能少于 6 个字符」的文案。
    """
    # loc 形如 ("body", "password")，去掉来源前缀只留字段路径
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
    elif error_type == "string_pattern_mismatch":
        reason = "格式不正确"
    elif error_type == "int_parsing":
        reason = "必须是整数"
    elif error_type == "greater_than_equal":
        reason = f"不能小于 {ctx.get('ge', '?')}"
    elif error_type == "less_than_equal":
        reason = f"不能大于 {ctx.get('le', '?')}"
    elif error_type == "greater_than":
        reason = f"必须大于 {ctx.get('gt', '?')}"
    elif error_type in ("time_parsing", "time_type"):
        reason = "时间格式应为 HH:MM 或 HH:MM:SS"
    elif error_type == "literal_error":
        reason = f"只能是 {ctx.get('expected', '指定取值')}"
    elif error_type == "value_error":
        # 自定义 ValueError 会被 Pydantic 包成 "Value error, 具体原因"，这里剥掉前缀直接给中文
        raw = str(ctx.get("error") or error.get("msg") or "")
        reason = raw.removeprefix("Value error, ") or "取值不合法"
    else:
        # 没覆盖到的类型保留 Pydantic 原文，至少能看出问题
        reason = error.get("msg", "参数不合法")

    return f"{field}: {reason}" if field else reason


def register_exception_handlers(app: FastAPI) -> None:
    """注册全部异常处理器，在 ``main.py`` 里调用一次。"""

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """业务里主动 raise 的 HTTPException（401/403/404/409 等）。

        detail 是中文时原样透出；是框架默认英文（或空）时查表换成中文。
        """
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
        """入参校验失败：提取第一条错误拼成「字段: 原因」。

        data 里保留完整 errors，调试时前端/日志还能看到全部问题。
        """
        errors = exc.errors()
        message = _format_validation_error(errors[0]) if errors else "参数不合法"
        # ctx 里可能带异常对象（如自定义 ValueError），直接塞 JSONResponse 会序列化失败
        safe_errors = [
            {
                **error,
                "ctx": {key: str(value) for key, value in (error.get("ctx") or {}).items()},
            }
            for error in errors
        ]
        return JSONResponse(status_code=422, content=_body(422, message, data=safe_errors))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期异常记完整堆栈，对外只暴露通用提示，避免泄内部信息。"""
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_body(500, "服务器内部错误，请稍后重试"))
