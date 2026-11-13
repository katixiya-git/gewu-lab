"""统一响应信封：所有接口返回 ``{code, message, data}``。

前端约定：``code == 200`` 表示成功，直接取 ``data``；非 200 弹 ``message``；
401 由前端拦截器清登录态并跳登录页。
"""

from typing import Generic, TypeVar

from app.schemas.common import CamelModel

T = TypeVar("T")


class Result(CamelModel, Generic[T]):
    """统一响应结构。

    - code：业务状态码，成功固定 200，失败复用 HTTP 状态码（401/403/404/422/500）
    - message：给人看的提示
    - data：业务数据，失败时为 null
    """

    code: int = 200
    message: str = "success"
    data: T | None = None

    @classmethod
    def ok(cls, data: T | None = None, message: str = "success") -> "Result[T]":
        """构造成功响应。

        Args:
            data: 业务数据，可为 None。
            message: 提示文案，默认 ``success``。

        Returns:
            Result[T]: code=200 的信封。
        """
        return cls(code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: int, message: str, data: T | None = None) -> "Result[T]":
        """构造失败响应。

        Args:
            code: 业务状态码（与 HTTP 状态码保持一致）。
            message: 面向用户的错误说明。
            data: 可选的附加信息（如校验错误明细）。

        Returns:
            Result[T]: code 为传入值的信封。
        """
        return cls(code=code, message=message, data=data)
