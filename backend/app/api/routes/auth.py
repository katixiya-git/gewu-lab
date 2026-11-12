"""登录与当前用户接口。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.result import Result
from app.core.security import create_access_token, verify_password
from app.db import get_session
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 登录
@router.post("/login", response_model=Result[LoginResponse], summary="账号密码登录")
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> Result[LoginResponse]:
    user = await session.scalar(select(User).where(User.username == body.username))

    # 用户不存在与密码错误返回同一提示，避免暴露账号是否存在
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用，请联系管理员",
        )

    token = create_access_token(user.id, user.role)
    return Result.ok(LoginResponse(access_token=token, user=UserOut.model_validate(user)))

# 获取当前登录用户
@router.get("/me", response_model=Result[UserOut], summary="当前登录用户")
async def me(current_user: User = Depends(get_current_user)) -> Result[UserOut]:
    return Result.ok(UserOut.model_validate(current_user))
