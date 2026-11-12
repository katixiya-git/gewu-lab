"""登录相关的请求/响应模型。"""

from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.user import UserOut


class UpdateProfileRequest(CamelModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=32)
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    avatar: Optional[str] = Field(default=None, max_length=255, description="头像 URL")


class LoginRequest(CamelModel):
    username: str = Field(min_length=1, max_length=32, examples=["admin"])
    password: str = Field(min_length=6, max_length=64, examples=["123456"])


class RegisterRequest(CamelModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    name: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    phone: Optional[str] = Field(default=None, pattern=r"^1[3-9]\d{9}$")
    email: Optional[str] = Field(
        default=None, max_length=128, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )


class LoginResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
