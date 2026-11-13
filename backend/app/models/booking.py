"""预约表 ORM 模型。

一张预约单对应「一个学生 + 一间实验室 + 一个日期 + 一个时段」。
状态流转见 ``app.services.booking_service``；这里只描述表结构与约束。

- ``bookings``：预约主表，保存申请人、实验室、时间、状态与审核信息
- ``booking_devices``：预约用到哪些设备（多对多），删除预约时级联清理
"""

from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Booking(Base):
    """预约主表。"""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_lab_date_status", "lab_id", "booking_date", "status"),
        Index("ix_bookings_user_status", "user_id", "status"),
        {"comment": "预约表"},
    )

    code: Mapped[str] = mapped_column(
        String(24),
        unique=True,
        index=True,
        nullable=False,
        comment="预约号，形如 BK202611130001",
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="申请人",
    )

    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="实验室",
    )

    booking_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="预约日期",
    )

    start_time: Mapped[time] = mapped_column(Time, nullable=False, comment="开始时间")
    end_time: Mapped[time] = mapped_column(Time, nullable=False, comment="结束时间")

    people_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="使用人数",
    )

    booking_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="personal",
        server_default="personal",
        comment="类型：personal / group / class",
    )

    purpose: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="用途说明",
    )

    contact_name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="联系人姓名",
    )

    contact_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="联系电话",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
        comment="pending / approved / rejected / conflict / cancelled",
    )

    reject_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="驳回理由，或取消申请被拒时的说明",
    )

    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="是否有待处理的取消申请",
    )

    cancel_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="取消或申请取消的理由",
    )

    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人",
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="审核时间",
    )


class BookingDevice(Base):
    """预约与设备的关联表。"""

    __tablename__ = "booking_devices"
    __table_args__ = (
        UniqueConstraint("booking_id", "device_id", name="uq_booking_devices"),
        {"comment": "预约设备关联表"},
    )

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="预约 id",
    )

    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="设备 id",
    )
