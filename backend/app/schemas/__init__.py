"""请求/响应模型包：统一导出，路由与服务层按需引用。"""

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UpdateProfileRequest,
)
from app.schemas.common import CamelModel
from app.schemas.device import (
    DeviceCreateRequest,
    DeviceOut,
    DevicePageOut,
    DeviceStatusRequest,
    DeviceUpdateRequest,
)
from app.schemas.file import FileOut
from app.schemas.lab import (
    LabCreateRequest,
    LabOut,
    LabPageOut,
    LabStatusRequest,
    LabUpdateRequest,
)
from app.schemas.user import (
    UserCreateRequest,
    UserOut,
    UserPageOut,
    UserUpdateRequest,
)

__all__ = [
    "CamelModel",
    "ChangePasswordRequest",
    "DeviceCreateRequest",
    "DeviceOut",
    "DevicePageOut",
    "DeviceStatusRequest",
    "DeviceUpdateRequest",
    "FileOut",
    "LabCreateRequest",
    "LabOut",
    "LabPageOut",
    "LabStatusRequest",
    "LabUpdateRequest",
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "UpdateProfileRequest",
    "UserCreateRequest",
    "UserOut",
    "UserPageOut",
    "UserUpdateRequest",
]
