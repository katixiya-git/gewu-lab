"""实验室相关的请求/响应模型。

校验尽量放在这一层（长度、枚举、时间先后），业务规则（重名、状态切换）
留给 service；这样接口层拿到的入参已经是干净数据，422 也能直接给前端看。
"""

import re
from datetime import datetime, time
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.common import CamelModel

# 类型码与状态码用 Literal：写错直接 422，不用等到业务层再判断
LabCategory = Literal["ai", "robot", "cloud", "se"]
LabStatus = Literal["enabled", "disabled"]

# 开放日只允许「1-7」或「1-5」这种闭区间写法
_OPEN_DAYS_RE = re.compile(r"^([1-7])(?:-([1-7]))?$")


def _check_open_days(value: str) -> str:
    """校验开放日格式，并保证起始日不晚于结束日。

    Args:
        value: 形如 ``"1-5"``、``"1-6"`` 或单日 ``"7"`` 的字符串。

    Returns:
        str: 原样返回，方便直接在 validator 里 return。

    Raises:
        ValueError: 格式不合法，或起始日晚于结束日。
    """
    matched = _OPEN_DAYS_RE.fullmatch(value)
    if matched is None:
        raise ValueError("开放日格式应为 1-7 或 1-5")
    start, end = matched.group(1), matched.group(2)
    if end is not None and int(start) > int(end):
        raise ValueError("开放日的起始日不能晚于结束日")
    return value


class LabOut(CamelModel):
    """返回给前端的实验室信息。

    ``open_time``/``close_time`` 是 ``time`` 类型，序列化后形如 ``"08:00:00"``；
    「周一至周五 08:00-22:00」这种展示文案由前端根据字段拼。
    """

    id: int
    name: str
    category: str
    location: str
    capacity: int
    open_days: str
    open_time: time
    close_time: time
    rule: str | None = None
    description: str | None = None
    cover_image: str | None = None
    status: str
    sort_order: int
    create_time: datetime


class LabCreateRequest(CamelModel):
    """管理员新增实验室。

    - 名称全局唯一，重名由 service 返回 409，不在这里查库
    - 结束时间必须晚于开始时间
    - 规则/简介可空，上限 2000 字符，避免把整篇文档塞进来
    """

    name: str = Field(min_length=1, max_length=64)
    category: LabCategory
    location: str = Field(default="", max_length=128)
    capacity: int = Field(ge=1, le=500)
    open_days: str = Field(default="1-5")
    open_time: time
    close_time: time
    rule: Optional[str] = Field(default=None, max_length=2000)
    description: Optional[str] = Field(default=None, max_length=2000)
    cover_image: Optional[str] = Field(default=None, max_length=255)
    status: LabStatus = "enabled"
    sort_order: int = Field(default=0, ge=0, le=9999)

    @field_validator("open_days")
    @classmethod
    def validate_open_days(cls, value: str) -> str:
        """复用开放日校验，把错误提前到 422。"""
        return _check_open_days(value)

    @model_validator(mode="after")
    def validate_time_range(self) -> "LabCreateRequest":
        """跨字段校验：结束时间必须晚于开始时间。"""
        if self.close_time <= self.open_time:
            raise ValueError("开放结束时间必须晚于开始时间")
        return self


class LabUpdateRequest(CamelModel):
    """管理员编辑实验室；只提交需要修改的字段。

    服务层用 ``model_dump(exclude_unset=True)`` 区分「没传（不改）」与
    「显式传 null（清空）」。只传开始或结束时，由 service 合并旧值后再
    校验时间先后，这里只校验单字段格式。
    """

    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    category: Optional[LabCategory] = None
    location: Optional[str] = Field(default=None, max_length=128)
    capacity: Optional[int] = Field(default=None, ge=1, le=500)
    open_days: Optional[str] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    rule: Optional[str] = Field(default=None, max_length=2000)
    description: Optional[str] = Field(default=None, max_length=2000)
    cover_image: Optional[str] = Field(default=None, max_length=255)
    status: Optional[LabStatus] = None
    sort_order: Optional[int] = Field(default=None, ge=0, le=9999)

    @field_validator("open_days")
    @classmethod
    def validate_open_days(cls, value: Optional[str]) -> Optional[str]:
        """开放日只在传了的时候校验。"""
        return None if value is None else _check_open_days(value)


class LabStatusRequest(CamelModel):
    """启用 / 停用实验室，单独一个轻量入参。"""

    status: LabStatus


class LabPageOut(CamelModel):
    """分页结果：总数 + 当前页数据。"""

    total: int
    items: list[LabOut]
