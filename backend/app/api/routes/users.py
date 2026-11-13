"""用户管理接口：只做参数接收、鉴权与响应封装。

业务实现在 ``app.services.user_service.UserService``。
"""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_admin, get_user_service
from app.core.result import Result
from app.models import User
from app.schemas import UserCreateRequest, UserOut, UserPageOut, UserUpdateRequest
from app.services import UserService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/page",
    response_model=Result[UserPageOut],
    summary="分页查询用户",
    description="管理员分页浏览用户；keyword 会同时模糊匹配用户名、姓名、手机号、邮箱。",
)
async def page_users(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: str | None = Query(
        None, max_length=50, description="用户名/姓名/手机号/邮箱模糊搜索"
    ),
    role: str | None = Query(None, description="按角色过滤：student / admin"),
    status_filter: str | None = Query(
        None, alias="status", description="按状态过滤：active / disabled"
    ),
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
) -> Result[UserPageOut]:
    """按条件分页查询用户。

    keyword、role、status 均可省略；role/status 传入非法值时忽略该条件，
    不返回 422。

    Args:
        page: 页码，从 1 开始。
        size: 每页条数，1–100。
        keyword: 可选关键词，最长 50 字符，匹配用户名/姓名/手机号/邮箱。
        role: 可选的角色过滤，``student`` 或 ``admin``。
        status_filter: 可选的状态过滤，``active`` 或 ``disabled``。
        _: 管理员鉴权依赖，学生调用返回 403。
        service: 用户业务服务（依赖注入）。

    Returns:
        Result[UserPageOut]: code=200，data 含 total 与当前页 items。

    Raises:
        HTTPException 401: 未登录或令牌失效。
        HTTPException 403: 当前账号不是管理员。
    """
    data = await service.page(
        page=page, size=size, keyword=keyword, role=role, status_filter=status_filter
    )
    return Result.ok(data)


@router.post(
    "",
    response_model=Result[UserOut],
    status_code=status.HTTP_201_CREATED,
    summary="新增用户",
    description="管理员创建账号，可指定角色与状态；密码不传时默认 123456。",
)
async def create_user(
    body: UserCreateRequest,
    _: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
) -> Result[UserOut]:
    """创建用户。

    Args:
        body: 新用户的账号、姓名、密码、角色、状态及联系方式。
        _: 管理员鉴权依赖，学生调用返回 403。
        service: 用户业务服务（依赖注入）。

    Returns:
        Result[UserOut]: code=200，data 为创建成功的用户信息。

    Raises:
        HTTPException 409: 用户名、手机号或邮箱已被占用。
        HTTPException 422: 字段格式不合法（如手机号不是 11 位）。
    """
    return Result.ok(await service.create(body))


@router.put(
    "/{user_id}",
    response_model=Result[UserOut],
    summary="编辑用户",
    description="修改姓名、角色、状态、手机号、邮箱或头像；只提交需要变更的字段。",
)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    admin: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
) -> Result[UserOut]:
    """编辑指定用户。

    只处理请求中显式提交的字段；字段传 null 表示清空。安全规则：不能停用
    当前登录账号；最后一名启用中的管理员不能被降级或停用。

    Args:
        user_id: 目标用户主键。
        body: 待修改的姓名、角色、状态、手机号、邮箱或头像。
        admin: 发起操作的管理员（鉴权依赖）。
        service: 用户业务服务（依赖注入）。

    Returns:
        Result[UserOut]: code=200，data 为更新后的用户信息。

    Raises:
        HTTPException 400: 停用当前登录账号，或触碰最后一名管理员保护。
        HTTPException 404: 目标用户不存在。
        HTTPException 409: 手机号或邮箱已被其他账号占用。
    """
    return Result.ok(await service.update(user_id, body, admin))


@router.delete(
    "/{user_id}",
    response_model=Result[None],
    summary="删除用户",
    description="物理删除账号；不能删除自己，也不能删掉最后一名启用中的管理员。",
)
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    service: UserService = Depends(get_user_service),
) -> Result[None]:
    """删除指定用户（物理删除，不可恢复）。

    Args:
        user_id: 目标用户主键。
        admin: 发起操作的管理员（鉴权依赖）。
        service: 用户业务服务（依赖注入）。

    Returns:
        Result[None]: code=200，无业务数据。

    Raises:
        HTTPException 400: 删除自己，或触碰最后一名管理员保护。
        HTTPException 404: 用户不存在。
    """
    await service.delete(user_id, admin)
    return Result.ok(None)
