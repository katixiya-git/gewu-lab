"""认证相关业务逻辑：登录、注册、资料与密码修改。"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UpdateProfileRequest,
    UserOut,
)


class AuthService:
    """认证与账号自助操作的领域逻辑。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def login(self, body: LoginRequest) -> LoginResponse:
        user = await self.session.scalar(
            select(User).where(User.username == body.username)
        )

        # 用户不存在与密码错误返回同一提示，避免暴露账号是否存在
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
            )

        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员"
            )

        token = create_access_token(user.id, user.role)
        return LoginResponse(access_token=token, user=UserOut.model_validate(user))

    async def register(self, body: RegisterRequest) -> LoginResponse:
        exists = await self.session.scalar(
            select(User).where(User.username == body.username)
        )
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册"
            )

        # 自助注册只开放学生角色，管理员账号由后台创建
        user = User(
            username=body.username,
            name=body.name,
            password_hash=hash_password(body.password),
            role="student",
            status="active",
            phone=body.phone or None,
            email=body.email or None,
        )
        self.session.add(user)

        try:
            await self.session.commit()
        except IntegrityError:
            # username / phone / email 上有唯一索引，并发注册时兜底
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名、手机号或邮箱已被注册",
            )

        await self.session.refresh(user)
        token = create_access_token(user.id, user.role)
        return LoginResponse(access_token=token, user=UserOut.model_validate(user))

    async def update_profile(
        self, user: User, body: UpdateProfileRequest
    ) -> UserOut:
        data = body.model_dump(exclude_unset=True)

        if data.get("name") is not None:
            user.name = data["name"]
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

    async def change_password(
        self, user: User, body: ChangePasswordRequest
    ) -> None:
        if not verify_password(body.old_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确"
            )
        if body.old_password == body.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与当前密码相同",
            )

        user.password_hash = hash_password(body.new_password)
        await self.session.commit()
