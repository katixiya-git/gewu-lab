"""用户管理业务逻辑：分页查询、增删改与管理员保护规则。"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User
from app.schemas import UserCreateRequest, UserOut, UserPageOut, UserUpdateRequest


class UserService:
    """用户管理的领域逻辑，路由层只负责收参、鉴权和返回信封。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def page(
        self,
        *,
        page: int,
        size: int,
        keyword: str | None,
        role: str | None,
        status_filter: str | None,
    ) -> UserPageOut:
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

        total = (
            await self.session.scalar(
                select(func.count()).select_from(User).where(*conditions)
            )
            or 0
        )

        users = (
            await self.session.scalars(
                select(User)
                .where(*conditions)
                .order_by(User.id)
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()

        return UserPageOut(
            total=total, items=[UserOut.model_validate(user) for user in users]
        )

    async def create(self, body: UserCreateRequest) -> UserOut:
        exists = await self.session.scalar(
            select(User).where(User.username == body.username)
        )
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册"
            )

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
        self.session.add(user)

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名、手机号或邮箱已被占用",
            )

        await self.session.refresh(user)
        return UserOut.model_validate(user)

    async def update(
        self, user_id: int, body: UserUpdateRequest, operator: User
    ) -> UserOut:
        user = await self._get_or_404(user_id)
        data = body.model_dump(exclude_unset=True)

        if user.id == operator.id and data.get("status") == "disabled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用当前登录账号"
            )

        losing_admin = (data.get("role") == "student") or (
            data.get("status") == "disabled"
        )
        if user.role == "admin" and user.status == "active" and losing_admin:
            if await self._count_active_admins() <= 1:
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
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="手机号或邮箱已被占用",
            )

        await self.session.refresh(user)
        return UserOut.model_validate(user)

    async def delete(self, user_id: int, operator: User) -> None:
        user = await self._get_or_404(user_id)

        if user.id == operator.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号"
            )
        if user.role == "admin" and user.status == "active":
            if await self._count_active_admins() <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="至少保留一名启用状态的管理员",
                )

        await self.session.delete(user)
        await self.session.commit()

    async def _get_or_404(self, user_id: int) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在"
            )
        return user

    async def _count_active_admins(self) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == "admin", User.status == "active")
            )
            or 0
        )
