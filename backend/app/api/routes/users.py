"""管理员用户管理：分页查询、模糊搜索、增删改。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.result import Result
from app.core.security import hash_password
from app.db import get_session
from app.models import User
from app.schemas import UserCreateRequest, UserOut, UserPageOut, UserUpdateRequest

router = APIRouter(prefix="/api/users", tags=["users"])

_active_admin_count = (
    select(func.count())
    .select_from(User)
    .where(User.role == "admin", User.status == "active")
)


async def _count_active_admins(session: AsyncSession) -> int:
    return await session.scalar(_active_admin_count) or 0


async def _get_user_or_404(user_id: int, session: AsyncSession) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.get("/page", response_model=Result[UserPageOut], summary="分页查询用户")
async def page_users(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(None, max_length=50, description="用户名/姓名/手机号/邮箱模糊搜索"),
    role: str | None = Query(None, description="按角色过滤：student / admin"),
    status_filter: str | None = Query(None, alias="status", description="按状态过滤：active / disabled"),
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Result[UserPageOut]:
    conditions = []

    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        conditions.append(
            or_(
                User.username.like(like),
                User.name.like(like),
                User.phone.like(like),
                User.email.like(like),
            )
        )
    if role in ("student", "admin"):
        conditions.append(User.role == role)
    if status_filter in ("active", "disabled"):
        conditions.append(User.status == status_filter)

    total = await session.scalar(
        select(func.count()).select_from(User).where(*conditions)
    ) or 0

    users = (
        await session.scalars(
            select(User)
            .where(*conditions)
            .order_by(User.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()

    return Result.ok(
        UserPageOut(total=total, items=[UserOut.model_validate(u) for u in users])
    )


@router.post("", response_model=Result[UserOut], status_code=status.HTTP_201_CREATED, summary="新增用户")
async def create_user(
    body: UserCreateRequest,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Result[UserOut]:
    exists = await session.scalar(select(User).where(User.username == body.username))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册")

    user = User(
        username=body.username,
        name=body.name,
        password_hash=hash_password(body.password),
        role=body.role,
        status=body.status,
        phone=body.phone or None,
        email=body.email or None,
        avatar=body.avatar or None,
    )
    session.add(user)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名、手机号或邮箱已被占用",
        )
    await session.refresh(user)
    return Result.ok(UserOut.model_validate(user))


@router.put("/{user_id}", response_model=Result[UserOut], summary="编辑用户")
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Result[UserOut]:
    user = await _get_user_or_404(user_id, session)
    data = body.model_dump(exclude_unset=True)

    if user.id == admin.id and data.get("status") == "disabled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前登录账号")

    # 最后一名启用中的管理员不能被降级或停用，否则系统将无人可管
    losing_admin = (data.get("role") == "student") or (data.get("status") == "disabled")
    if user.role == "admin" and user.status == "active" and losing_admin:
        if await _count_active_admins(session) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少保留一名启用状态的管理员",
            )

    if "name" in data and data["name"] is not None:
        user.name = data["name"]
    for field in ("role", "status"):
        if data.get(field) is not None:
            setattr(user, field, data[field])
    for field in ("phone", "email", "avatar"):
        if field in data:
            setattr(user, field, data[field] or None)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="手机号或邮箱已被占用",
        )
    await session.refresh(user)
    return Result.ok(UserOut.model_validate(user))


@router.delete("/{user_id}", response_model=Result[None], summary="删除用户")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> Result[None]:
    user = await _get_user_or_404(user_id, session)

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号")
    if user.role == "admin" and user.status == "active":
        if await _count_active_admins(session) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少保留一名启用状态的管理员",
            )

    await session.delete(user)
    await session.commit()
    return Result.ok(None)
