"""统一响应信封：所有接口返回 {code, message, data}。"""

from typing import Generic, TypeVar

from app.schemas.common import CamelModel

T = TypeVar("T")


class Result(CamelModel, Generic[T]):
    """统一响应结构。

    - code：业务状态码，成功固定 200，失败复用 HTTP 状态码
    - message：给人看的提示
    - data：业务数据，失败时为 null
    """

    code: int = 200
    message: str = "success"
    data: T | None = None

    @classmethod
    def ok(cls, data: T | None = None, message: str = "success") -> "Result[T]":
        return cls(code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: int, message: str, data: T | None = None) -> "Result[T]":
        return cls(code=code, message=message, data=data)
