"""用户管理业务逻辑：分页查询、增删改与管理员保护规则。

本模块只处理业务规则与数据读写，不感知 HTTP 路由；接口层见
``app.api.routes.users``。
"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User
from app.schemas import UserCreateRequest, UserOut, UserPageOut, UserUpdateRequest


class UserService:
    """用户管理的业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        """Args:
            session: 由接口层依赖注入的异步数据库会话。
        """
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
        """按条件分页查询用户。

        ``keyword`` 会同时模糊匹配用户名、姓名、手机号与邮箱；
        ``role``、``status`` 传入非法值时忽略该条件，不报错。

        Args:
            page: 页码，从 1 开始。
            size: 每页条数，1–100。
            keyword: 可选的关键词，最长 50 字符。
            role: 可选的角色过滤，``student`` 或 ``admin``。
            status_filter: 可选的状态过滤，``active`` 或 ``disabled``。

        Returns:
            UserPageOut: 总条数与当前页用户列表。
        """
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
        """创建用户。

        密码不传时使用默认值 ``123456``；创建后即可登录。

        Args:
            body: 新用户的账号、姓名、密码、角色、状态与联系方式。

        Returns:
            UserOut: 创建成功的用户信息。

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
        """编辑指定用户。

        仅处理请求中显式提交的字段；字段传 ``null`` 表示清空。

        安全规则：
        1. 不能停用当前登录账号；
        2. 最后一名启用中的管理员不能被降级或停用。

        Args:
            user_id: 目标用户主键。
            body: 待修改的姓名、角色、状态、手机号、邮箱或头像。
            operator: 发起操作的管理员（由接口层鉴权后传入）。

        Returns:
            UserOut: 更新后的用户信息。

        Raises:
            HTTPException 404: 目标用户不存在。
            HTTPException 400: 停用自己，或触碰最后一名管理员保护。
            HTTPException 409: 手机号或邮箱与其他账号冲突。
        """
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
        """删除指定用户（物理删除，不可恢复）。

        安全规则：不能删除自己，也不能删掉最后一名启用中的管理员。

        Args:
            user_id: 目标用户主键。
            operator: 发起操作的管理员（由接口层鉴权后传入）。

        Raises:
            HTTPException 404: 目标用户不存在。
            HTTPException 400: 删除自己，或触碰最后一名管理员保护。
        """
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
        """按主键取用户，不存在时抛 404。

        Args:
            user_id: 用户主键。

        Returns:
            User: 用户 ORM 对象。

        Raises:
            HTTPException 404: 用户不存在。
        """
        user = await self.session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在"
            )
        return user

    async def _count_active_admins(self) -> int:
        """统计启用状态的管理员数量，用于管理员保护规则。

        Returns:
            int: 启用中的管理员人数。
        """
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == "admin", User.status == "active")
            )
            or 0
        )
