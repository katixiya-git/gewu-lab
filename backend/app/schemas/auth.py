"""登录相关的请求/响应模型。"""

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.user import UserOut


class LoginRequest(CamelModel):
    username: str = Field(min_length=1, max_length=32, examples=["admin"])
    password: str = Field(min_length=6, max_length=64, examples=["123456"])


class LoginResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
