"""用户相关的响应模型。"""

from datetime import datetime

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
