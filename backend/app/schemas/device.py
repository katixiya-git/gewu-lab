"""设备相关的请求/响应模型。

设备名在同一实验室内唯一、实验室是否存在这类跨表规则放在 service；
这里只做单字段格式校验，保证进 service 的数据已经干净。
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from app.schemas.common import CamelModel

DeviceStatus = Literal["normal", "maintenance", "disabled"]


class DeviceOut(CamelModel):
    """返回给前端的设备信息；``lab_name`` 由 service 联表补齐。"""

    id: int
    lab_id: int
    lab_name: str
    name: str
    model: str | None = None
    total_count: int
    status: str
    note: str | None = None
    sort_order: int
    create_time: datetime


class DeviceCreateRequest(CamelModel):
    """管理员新增设备。

    - ``lab_id`` 是否存在、同实验室是否重名，由 service 查库判断
    - 数量限 1–999，避免误填把「台」写成「万台」
    """

    lab_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=64)
    model: Optional[str] = Field(default=None, max_length=64)
    total_count: int = Field(default=1, ge=1, le=999)
    status: DeviceStatus = "normal"
    note: Optional[str] = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0, le=9999)


class DeviceUpdateRequest(CamelModel):
    """管理员编辑设备；只提交需要修改的字段。"""

    lab_id: Optional[int] = Field(default=None, ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    model: Optional[str] = Field(default=None, max_length=64)
    total_count: Optional[int] = Field(default=None, ge=1, le=999)
    status: Optional[DeviceStatus] = None
    note: Optional[str] = Field(default=None, max_length=255)
    sort_order: Optional[int] = Field(default=None, ge=0, le=9999)


class DeviceStatusRequest(CamelModel):
    """单独切换设备状态。"""

    status: DeviceStatus


class DevicePageOut(CamelModel):
    """分页结果：总数 + 当前页数据。"""

    total: int
    items: list[DeviceOut]
