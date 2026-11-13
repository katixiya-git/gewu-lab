"""接口层通用依赖：登录校验、管理员校验与 Service 装配。

依赖链：``get_session``（一次请求一个数据库会话）→ Service；
鉴权依赖从请求头 ``Authorization: Bearer <token>`` 取 JWT，换取当前用户。
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db import get_session
from app.models import User
from app.services import AuthService, DeviceService, FileService, LabService, UserService

# auto_error=False：没带 token 时不在这里抛错，统一由下面返回中文提示
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """校验 Bearer token 并返回当前用户。

    令牌缺失、格式错误、过期、签名不符、用户不存在，一律 401；账号被停用 403。

    Args:
        credentials: HTTPBearer 解析出的凭据，没有则为 None。
        session: 数据库会话（依赖注入）。

    Returns:
        User: 当前登录用户 ORM 对象。

    Raises:
        HTTPException 401: 未携带令牌或令牌无效。
        HTTPException 403: 账号已被停用。
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已失效，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])  # sub 存的是字符串，转回 int 查库
    # 覆盖：签名/过期错误、payload 缺 sub、sub 不是数字
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized

    user = await session.get(User, user_id)
    if user is None:
        raise unauthorized
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")

    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """在已登录基础上要求管理员角色。

    Args:
        user: 已通过 ``get_current_user`` 校验的用户。

    Returns:
        User: 管理员用户。

    Raises:
        HTTPException 403: 当前账号不是管理员。
    """
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    """构造认证业务服务（每个请求一个实例）。"""
    return AuthService(session)


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    """构造用户业务服务（每个请求一个实例）。"""
    return UserService(session)


def get_file_service(session: AsyncSession = Depends(get_session)) -> FileService:
    """构造文件业务服务（每个请求一个实例）。"""
    return FileService(session)


def get_lab_service(session: AsyncSession = Depends(get_session)) -> LabService:
    """构造实验室业务服务（每个请求一个实例）。"""
    return LabService(session)


def get_device_service(session: AsyncSession = Depends(get_session)) -> DeviceService:
    """构建设备业务服务（每个请求一个实例）。"""
    return DeviceService(session)
