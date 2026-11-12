"""登录与当前用户接口。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.result import Result
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_session
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UpdateProfileRequest,
    UserOut,
)

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

# 学生注册（自助注册只开放学生角色，管理员账号由后台创建）
@router.post("/register", response_model=Result[LoginResponse], summary="学生注册")
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> Result[LoginResponse]:
    exists = await session.scalar(select(User).where(User.username == body.username))
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已被注册",
        )

    user = User(
        username=body.username,
        name=body.name,
        password_hash=hash_password(body.password),
        role="student",
        status="active",
        phone=body.phone or None,
        email=body.email or None,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # username / phone / email 上有唯一索引，并发注册时兜底
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名、手机号或邮箱已被注册",
        )
    await session.refresh(user)

    token = create_access_token(user.id, user.role)
    return Result.ok(LoginResponse(access_token=token, user=UserOut.model_validate(user)))

# 更新个人资料（姓名、手机号、邮箱、头像）
@router.put("/me", response_model=Result[UserOut], summary="更新个人资料")
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Result[UserOut]:
    data = body.model_dump(exclude_unset=True)

    if data.get("name") is not None:
        current_user.name = data["name"]
    for field in ("phone", "email", "avatar"):
        if field in data:
            setattr(current_user, field, data[field] or None)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="手机号或邮箱已被占用",
        )
    await session.refresh(current_user)
    return Result.ok(UserOut.model_validate(current_user))

# 修改密码
@router.put("/password", response_model=Result[None], summary="修改密码")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Result[None]:
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    if body.old_password == body.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与当前密码相同")

    current_user.password_hash = hash_password(body.new_password)
    await session.commit()
    return Result.ok(None)


# 获取当前登录用户
@router.get("/me", response_model=Result[UserOut], summary="当前登录用户")
async def me(current_user: User = Depends(get_current_user)) -> Result[UserOut]:
    return Result.ok(UserOut.model_validate(current_user))
