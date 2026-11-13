"""预约相关的请求 / 响应模型。

时间统一用 ``time`` 入参（``"14:00"`` 也能被 pydantic 解析），响应里再格式化成
``"14:00"``；日期用 ``date``，前端传 ``"2026-11-20"`` 即可。
"""

from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import Field, field_serializer

from app.schemas.common import CamelModel

BookingType = Literal["personal", "group", "class"]
BookingStatus = Literal["pending", "approved", "rejected", "conflict", "cancelled"]

# 展示文案，前端也可以自己映射；这里主要给接口文档用
BOOKING_TYPE_LABELS = {"personal": "个人", "group": "小组", "class": "班级"}
BOOKING_STATUS_LABELS = {
    "pending": "待审核",
    "approved": "已通过",
    "rejected": "已驳回",
    "conflict": "冲突待协调",
    "cancelled": "已取消",
}


def _hm(value: time) -> str:
    """把 time 格式化成 ``HH:MM``，去掉秒。"""
    return value.strftime("%H:%M")


class BookingDeviceOut(CamelModel):
    """预约里用到的设备（精简信息）。"""

    id: int
    name: str
    model: Optional[str] = None


class BookingOut(CamelModel):
    """返回给前端的一条预约。"""

    id: int
    code: str
    user_id: int
    user_name: str
    lab_id: int
    lab_name: str
    booking_date: date
    start_time: time
    end_time: time
    duration_minutes: int
    people_count: int
    booking_type: str
    purpose: Optional[str] = None
    contact_name: str
    contact_phone: str
    status: str
    reject_reason: Optional[str] = None
    cancel_requested: bool
    cancel_reason: Optional[str] = None
    devices: list[BookingDeviceOut] = Field(default_factory=list)
    create_time: datetime
    reviewed_at: Optional[datetime] = None

    @field_serializer("start_time", "end_time")
    def serialize_time(self, value: time) -> str:
        """时间统一输出 ``HH:MM``，避免前端处理 ``HH:MM:SS``。"""
        return _hm(value)


class BookingCreateRequest(CamelModel):
    """学生提交预约。"""

    lab_id: int = Field(ge=1)
    booking_date: date
    start_time: time
    end_time: time
    people_count: int = Field(ge=1, le=500)
    booking_type: BookingType = "personal"
    purpose: Optional[str] = Field(default=None, max_length=255)
    contact_name: str = Field(min_length=1, max_length=32)
    contact_phone: str = Field(min_length=6, max_length=20)
    device_ids: list[int] = Field(default_factory=list, max_length=20)


class BookingReviewRequest(CamelModel):
    """管理员审核预约：通过或驳回，驳回必须写理由。"""

    action: Literal["approve", "reject"]
    reason: Optional[str] = Field(default=None, max_length=255)


class BookingCancelRequest(CamelModel):
    """取消预约 / 提交取消申请时的理由，可选。"""

    reason: Optional[str] = Field(default=None, max_length=255)


class BookingCancelReviewRequest(CamelModel):
    """管理员处理学生的取消申请。"""

    approve: bool
    reason: Optional[str] = Field(default=None, max_length=255)


class BookingPageOut(CamelModel):
    """分页结果：总数 + 当前页数据。"""

    total: int
    items: list[BookingOut]
