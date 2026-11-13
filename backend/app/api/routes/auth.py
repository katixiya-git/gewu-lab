"""认证接口：只做参数接收、鉴权依赖与响应封装。

业务实现在 ``app.services.auth_service.AuthService``。
"""

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
    """账号密码登录。

    用户不存在与密码错误统一返回 401，避免暴露账号是否存在。

    Args:
        body: 登录账号与明文密码。
        service: 认证业务服务（依赖注入）。

    Returns:
        Result[LoginResponse]: code=200，data 含 accessToken、tokenType 与 user。

    Raises:
        HTTPException 401: 账号不存在或密码错误。
        HTTPException 403: 账号已被停用。
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

    Args:
        body: 用户名、姓名、密码及可选的手机号、邮箱。
        service: 认证业务服务（依赖注入）。

    Returns:
        Result[LoginResponse]: code=200，data 含新账号的令牌与用户信息。

    Raises:
        HTTPException 409: 用户名、手机号或邮箱已被占用。
        HTTPException 422: 字段格式不合法。
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

    Args:
        body: 待修改的姓名、手机号、邮箱或头像；未提交的字段保持不变。
        current_user: 当前登录用户（依赖注入）。
        service: 认证业务服务（依赖注入）。

    Returns:
        Result[UserOut]: code=200，data 为更新后的用户信息。

    Raises:
        HTTPException 409: 手机号或邮箱与其他账号冲突。
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

    修改成功后旧令牌在有效期内仍可使用，下次登录需要用新密码。

    Args:
        body: 当前密码与新密码。
        current_user: 当前登录用户（依赖注入）。
        service: 认证业务服务（依赖注入）。

    Returns:
        Result[None]: code=200，无业务数据。

    Raises:
        HTTPException 400: 当前密码不正确，或新密码与当前密码相同。
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
    """读取当前登录用户信息。

    Args:
        current_user: 当前登录用户（依赖注入）。

    Returns:
        Result[UserOut]: code=200，data 为用户信息（不含密码哈希）。
    """
    return Result.ok(UserOut.model_validate(current_user))
