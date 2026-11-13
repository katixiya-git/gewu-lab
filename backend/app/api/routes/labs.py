"""实验室管理接口：只做参数接收、鉴权与响应封装。

业务实现在 ``app.services.lab_service.LabService``：查询对所有登录用户开放，
新增/编辑/删除/启停仅管理员可用。
"""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_admin, get_current_user, get_lab_service
from app.core.result import Result
from app.models import User
from app.schemas import (
    LabCreateRequest,
    LabOut,
    LabPageOut,
    LabStatusRequest,
    LabUpdateRequest,
)
from app.services import LabService

router = APIRouter(prefix="/api/labs", tags=["labs"])


# GET /api/labs/page 分页查询实验室
# 管理员可看全部并按状态/类型筛选；学生只能看到 enabled 的实验室（status 参数被忽略）。
# keyword 同时模糊匹配名称与位置。
#
# Args:
#     page: 页码，从 1 开始。
#     size: 每页条数，1–50。
#     keyword: 可选关键词，最长 50 字符，匹配名称/位置。
#     category: 可选的类型过滤：ai / robot / cloud / se。
#     status_filter: 可选的状态过滤：enabled / disabled，仅管理员生效。
#     user: 当前登录用户（鉴权依赖）。
#     service: 实验室业务服务（依赖注入）。
#
# Returns:
#     Result[LabPageOut]: code=200，data 含 total 与当前页 items。
#
# Raises:
#     HTTPException 401: 未登录或令牌失效。
@router.get(
    "/page",
    response_model=Result[LabPageOut],
    summary="分页查询实验室",
    description="管理员可看全部并按状态筛选；学生只能看到启用中的实验室。",
)
async def page_labs(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=50, description="每页条数"),
    keyword: str | None = Query(None, max_length=50, description="名称/位置模糊搜索"),
    category: str | None = Query(None, description="按类型过滤：ai / robot / cloud / se"),
    status_filter: str | None = Query(
        None, alias="status", description="按状态过滤：enabled / disabled（仅管理员）"
    ),
    user: User = Depends(get_current_user),
    service: LabService = Depends(get_lab_service),
) -> Result[LabPageOut]:
    """按条件分页查询实验室。"""
    data = await service.page(
        current_user=user,
        page=page,
        size=size,
        keyword=keyword,
        category=category,
        status_filter=status_filter,
    )
    return Result.ok(data)


# GET /api/labs/{lab_id} 实验室详情
# 学生访问停用实验室会得到 404，视作不存在。
#
# Args:
#     lab_id: 实验室主键。
#     user: 当前登录用户（鉴权依赖）。
#     service: 实验室业务服务（依赖注入）。
#
# Returns:
#     Result[LabOut]: code=200，data 为实验室详情。
#
# Raises:
#     HTTPException 401: 未登录或令牌失效。
#     HTTPException 404: 实验室不存在（或学生访问停用实验室）。
@router.get(
    "/{lab_id}",
    response_model=Result[LabOut],
    summary="实验室详情",
    description="按 id 查询实验室；学生访问停用实验室返回 404。",
)
async def get_lab(
    lab_id: int,
    user: User = Depends(get_current_user),
    service: LabService = Depends(get_lab_service),
) -> Result[LabOut]:
    """查询单个实验室。"""
    return Result.ok(await service.get(lab_id, current_user=user))


# POST /api/labs 新增实验室
# 管理员创建实验室；名称全局唯一，重复返回 409。
# 结束时间必须晚于开始时间；capacity 限 1–500。
#
# Args:
#     body: 实验室名称、类型、位置、容量、开放日与时段、规则、封面等。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 实验室业务服务（依赖注入）。
#
# Returns:
#     Result[LabOut]: code=200，data 为创建成功的实验室。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 409: 实验室名称已存在。
#     HTTPException 422: 字段格式不合法（如结束时间早于开始时间）。
@router.post(
    "",
    response_model=Result[LabOut],
    status_code=status.HTTP_201_CREATED,
    summary="新增实验室",
    description="管理员创建实验室；名称唯一，结束时间必须晚于开始时间。",
)
async def create_lab(
    body: LabCreateRequest,
    _: User = Depends(get_current_admin),
    service: LabService = Depends(get_lab_service),
) -> Result[LabOut]:
    """创建实验室。"""
    return Result.ok(await service.create(body))


# PUT /api/labs/{lab_id} 编辑实验室
# 只修改请求中显式提交的字段；改时间时只需传开始或结束中的一个，服务层会用旧值补齐再校验。
#
# Args:
#     lab_id: 实验室主键。
#     body: 待修改字段，未传的保持不变。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 实验室业务服务（依赖注入）。
#
# Returns:
#     Result[LabOut]: code=200，data 为更新后的实验室。
#
# Raises:
#     HTTPException 400: 合并旧值后结束时间不晚于开始时间。
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 实验室不存在。
#     HTTPException 409: 新名称与其他实验室重复。
@router.put(
    "/{lab_id}",
    response_model=Result[LabOut],
    summary="编辑实验室",
    description="只提交需要变更的字段；改时间时服务层会用旧值补齐再校验先后。",
)
async def update_lab(
    lab_id: int,
    body: LabUpdateRequest,
    _: User = Depends(get_current_admin),
    service: LabService = Depends(get_lab_service),
) -> Result[LabOut]:
    """编辑指定实验室。"""
    return Result.ok(await service.update(lab_id, body))


# PUT /api/labs/{lab_id}/status 启用/停用实验室
# 停用后学生端列表与详情都不可见，已产生的历史预约不受影响（预约模块落地后生效）。
#
# Args:
#     lab_id: 实验室主键。
#     body: 目标状态，enabled 或 disabled。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 实验室业务服务（依赖注入）。
#
# Returns:
#     Result[LabOut]: code=200，data 为更新后的实验室。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 实验室不存在。
@router.put(
    "/{lab_id}/status",
    response_model=Result[LabOut],
    summary="启用/停用实验室",
    description="停用后学生端列表与详情都不可见。",
)
async def change_lab_status(
    lab_id: int,
    body: LabStatusRequest,
    _: User = Depends(get_current_admin),
    service: LabService = Depends(get_lab_service),
) -> Result[LabOut]:
    """切换实验室状态。"""
    return Result.ok(await service.change_status(lab_id, body))


# DELETE /api/labs/{lab_id} 删除实验室
# 物理删除，不可恢复；当前只校验存在性，预约模块落地后会补「存在未结束预约则拒绝删除」。
#
# Args:
#     lab_id: 实验室主键。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 实验室业务服务（依赖注入）。
#
# Returns:
#     Result[None]: code=200，无业务数据。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 实验室不存在。
@router.delete(
    "/{lab_id}",
    response_model=Result[None],
    summary="删除实验室",
    description="物理删除实验室；存在未结束预约时的保护逻辑待预约模块落地后补充。",
)
async def delete_lab(
    lab_id: int,
    _: User = Depends(get_current_admin),
    service: LabService = Depends(get_lab_service),
) -> Result[None]:
    """删除指定实验室。"""
    await service.delete(lab_id)
    return Result.ok(None)
