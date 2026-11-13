"""用户相关的请求/响应模型。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from app.schemas.common import CamelModel


class UserOut(CamelModel):
    """返回给前端的用户信息（不含密码哈希）。"""

    id: int
    username: str
    name: str
    role: str
    status: str
    avatar: str | None = None
    phone: str | None = None
    email: str | None = None
    create_time: datetime


class UserCreateRequest(CamelModel):
    """管理员新增用户。"""

    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    name: str = Field(min_length=1, max_length=32)
    password: str = Field(default="123456", min_length=6, max_length=64)
    role: Literal["student", "admin"] = "student"
    status: Literal["active", "disabled"] = "active"
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    avatar: Optional[str] = Field(default=None, max_length=255)


class UserUpdateRequest(CamelModel):
    """管理员编辑用户；只提交需要修改的字段。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=32)
    role: Optional[Literal["student", "admin"]] = None
    status: Optional[Literal["active", "disabled"]] = None
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    avatar: Optional[str] = Field(default=None, max_length=255)


class UserPageOut(CamelModel):
    """分页结果。"""

    total: int
    items: list[UserOut]
