"""实验室表 ORM 模型。

一间实验室对应「一个连续开放时段 + 一个开放日范围」，用于预约时的
开放时间校验。``category`` 存类型码（ai/robot/cloud/se），中文名由前端映射；
``status`` 为 ``disabled`` 时不可预约，也不会出现在学生端的可预约列表里。
"""

from datetime import time

from sqlalchemy import Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Lab(Base):
    """实验室：容量、开放时间、使用规则与封面。"""

    __tablename__ = "labs"
    __table_args__ = {"comment": "实验室"}

    name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="实验室名称",
    )

    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="类型：ai/robot/cloud/se",
    )

    location: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
        server_default="",
        comment="位置，如 实验楼A301",
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="容纳人数",
    )

    open_days: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1-5",
        server_default="1-5",
        comment="开放日：1-7，支持 1-5 这种范围",
    )

    open_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        comment="开放开始时间",
    )

    close_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
        comment="开放结束时间",
    )

    rule: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="使用规则",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="简介与设备概述",
    )

    cover_image: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="封面图 URL（/media/lab_cover/...）",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="enabled",
        server_default="enabled",
        index=True,
        comment="状态：enabled / disabled",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="排序，越小越靠前",
    )

    def __repr__(self) -> str:
        """便于日志里快速识别实验室。"""
        return f"<Lab id={self.id} name={self.name!r} status={self.status!r}>"
