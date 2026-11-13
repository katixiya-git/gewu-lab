"""认证业务逻辑：登录、注册、资料修改与密码修改。

本模块只处理业务规则与数据读写，不感知 HTTP 路由；接口层见
``app.api.routes.auth``。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
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
    """认证与账号自助操作的业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        """Args:
            session: 由接口层依赖注入的异步数据库会话。
        """
        self.session = session

    async def login(self, body: LoginRequest) -> LoginResponse:
        """校验账号密码并签发登录令牌。

        用户不存在与密码错误使用同一提示，避免暴露账号是否存在。

        Args:
            body: 登录账号与明文密码。

        Returns:
            LoginResponse: JWT、令牌类型与当前用户信息。

        Raises:
            HTTPException 401: 账号不存在或密码错误。
            HTTPException 403: 账号已被停用。
        """
        user = await self.session.scalar(
            select(User).where(User.username == body.username)
        )

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
        """学生自助注册，注册成功即登录。

        自助注册固定为 ``student`` 角色，管理员账号只能由后台创建。

        Args:
            body: 用户名、姓名、密码及可选的手机号、邮箱。

        Returns:
            LoginResponse: 新账号的 JWT 与用户信息。

        Raises:
            HTTPException 409: 用户名、手机号或邮箱已被占用。
        """
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

    async def update_profile(self, user: User, body: UpdateProfileRequest) -> UserOut:
        """更新当前登录用户的个人资料。

        仅处理请求中显式提交的字段（``exclude_unset``）；字段传 ``null``
        表示清空，传空字符串同样按清空处理。

        Args:
            user: 当前登录用户（由接口层鉴权后传入）。
            body: 待修改的姓名、手机号、邮箱或头像。

        Returns:
            UserOut: 更新后的用户信息。

        Raises:
            HTTPException 409: 手机号或邮箱与其他账号冲突。
        """
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

    async def change_password(self, user: User, body: ChangePasswordRequest) -> None:
        """修改当前登录用户的密码。

        修改成功后旧令牌在有效期内仍可使用，下次登录需要用新密码。

        Args:
            user: 当前登录用户（由接口层鉴权后传入）。
            body: 当前密码与新密码。

        Raises:
            HTTPException 400: 当前密码不正确，或新密码与当前密码相同。
        """
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
