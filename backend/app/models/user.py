from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    """系统用户：学生与管理员共用一张表，用 role 区分。"""

    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    username: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        comment="登录账号",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希（bcrypt）",
    )

    name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="显示姓名",
    )

    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="student",
        server_default="student",
        comment="角色：student / admin",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
        comment="状态：active / disabled",
    )

    avatar: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="头像 URL",
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True,
        comment="手机号",
    )

    email: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=True,
        comment="邮箱",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
