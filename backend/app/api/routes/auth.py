"""登录与当前用户接口：只做参数接收、鉴权与响应封装。"""

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user
from app.core.result import Result
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UpdateProfileRequest,
    UserOut,
)
from app.services import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=Result[LoginResponse],
    summary="账号密码登录",
    description="校验用户名与密码，成功返回 JWT（12 小时有效）和当前用户信息。",
)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> Result[LoginResponse]:
    """登录。

    用户不存在与密码错误统一返回 401「用户名或密码错误」，避免暴露账号是否存在；
    账号被停用时返回 403。
    """
    return Result.ok(await service.login(body))


@router.post(
    "/register",
    response_model=Result[LoginResponse],
    summary="学生注册",
    description="自助注册只开放学生角色；管理员账号由用户管理页创建。注册成功直接返回登录令牌。",
)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> Result[LoginResponse]:
    """学生自助注册。

    用户名、手机号、邮箱均唯一；用户名重复或唯一索引冲突时返回 409。
    """
    return Result.ok(await service.register(body))


@router.put(
    "/me",
    response_model=Result[UserOut],
    summary="更新个人资料",
    description="修改当前登录用户的姓名、手机号、邮箱或头像；只提交需要变更的字段。",
)
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Result[UserOut]:
    """更新当前登录用户的资料。

    手机号或邮箱与其他账号冲突时返回 409。
    """
    return Result.ok(await service.update_profile(current_user, body))


@router.put(
    "/password",
    response_model=Result[None],
    summary="修改密码",
    description="需要提供当前密码；新密码 6–64 位，且不能与当前密码相同。",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Result[None]:
    """修改当前登录用户的密码。

    当前密码不正确或新旧密码相同返回 400；成功后可继续使用旧令牌，下次登录改用新密码。
    """
    await service.change_password(current_user, body)
    return Result.ok(None)


@router.get(
    "/me",
    response_model=Result[UserOut],
    summary="当前登录用户",
    description="根据请求头中的 Bearer token 返回当前用户资料，前端刷新页面时用它恢复登录态。",
)
async def me(current_user: User = Depends(get_current_user)) -> Result[UserOut]:
    """读取当前登录用户信息（不含密码哈希）。"""
    return Result.ok(UserOut.model_validate(current_user))
