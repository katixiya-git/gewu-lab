"""登录相关的请求/响应模型。"""

from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.user import UserOut


class ChangePasswordRequest(CamelModel):
    """修改密码入参。

    旧密码只校验是否匹配；新密码 6–64 位，且不能与旧密码相同（服务层校验）。
    """

    old_password: str = Field(min_length=1, max_length=64, description="当前密码")
    new_password: str = Field(min_length=6, max_length=64, description="新密码")


class UpdateProfileRequest(CamelModel):
    """个人资料修改入参；未提交的字段保持不变。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=32)
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    avatar: Optional[str] = Field(default=None, max_length=255, description="头像 URL")


class LoginRequest(CamelModel):
    """登录入参：账号 + 明文密码（HTTPS 下传输）。"""

    username: str = Field(min_length=1, max_length=32, examples=["admin"])
    password: str = Field(min_length=6, max_length=64, examples=["123456"])


class RegisterRequest(CamelModel):
    """学生注册入参；管理员账号不开放自助注册。"""

    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    name: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )


class LoginResponse(CamelModel):
    """登录/注册成功的响应：令牌 + 用户信息。"""

    access_token: str
    token_type: str = "bearer"
    user: UserOut
