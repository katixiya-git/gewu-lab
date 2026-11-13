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


@router.post("/login", response_model=Result[LoginResponse], summary="账号密码登录")
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> Result[LoginResponse]:
    return Result.ok(await service.login(body))


@router.post("/register", response_model=Result[LoginResponse], summary="学生注册")
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> Result[LoginResponse]:
    return Result.ok(await service.register(body))


@router.put("/me", response_model=Result[UserOut], summary="更新个人资料")
async def update_me(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Result[UserOut]:
    return Result.ok(await service.update_profile(current_user, body))


@router.put("/password", response_model=Result[None], summary="修改密码")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Result[None]:
    await service.change_password(current_user, body)
    return Result.ok(None)


@router.get("/me", response_model=Result[UserOut], summary="当前登录用户")
async def me(current_user: User = Depends(get_current_user)) -> Result[UserOut]:
    return Result.ok(UserOut.model_validate(current_user))
