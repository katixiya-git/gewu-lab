"""设备管理接口：只做参数接收、鉴权与响应封装。

业务实现在 ``app.services.device_service.DeviceService``：查询对所有登录用户
开放（学生只能看到启用实验室的非停用设备），增删改仅管理员可用。
"""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_admin, get_current_user, get_device_service
from app.core.result import Result
from app.models import User
from app.schemas import (
    DeviceCreateRequest,
    DeviceOut,
    DevicePageOut,
    DeviceStatusRequest,
    DeviceUpdateRequest,
)
from app.services import DeviceService

router = APIRouter(prefix="/api/devices", tags=["devices"])


# GET /api/devices/page 分页查询设备
# 管理员可看全部并按状态/实验室筛选；学生只能看到启用实验室下、非停用的设备。
# keyword 同时模糊匹配设备名、型号与备注。
#
# Args:
#     page: 页码，从 1 开始。
#     size: 每页条数，1–50。
#     keyword: 可选关键词，最长 50 字符。
#     lab_id: 可选的实验室过滤。
#     status_filter: 可选状态过滤：normal / maintenance / disabled，仅管理员生效。
#     user: 当前登录用户（鉴权依赖）。
#     service: 设备业务服务（依赖注入）。
#
# Returns:
#     Result[DevicePageOut]: code=200，data 含 total 与当前页 items。
#
# Raises:
#     HTTPException 401: 未登录或令牌失效。
@router.get(
    "/page",
    response_model=Result[DevicePageOut],
    summary="分页查询设备",
    description="管理员可看全部并按状态/实验室筛选；学生只能看到启用实验室下的可用设备。",
)
async def page_devices(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=50, description="每页条数"),
    keyword: str | None = Query(None, max_length=50, description="名称/型号/备注模糊搜索"),
    lab_id: int | None = Query(None, alias="labId", description="按实验室过滤"),
    status_filter: str | None = Query(
        None, alias="status", description="按状态过滤：normal / maintenance / disabled（仅管理员）"
    ),
    user: User = Depends(get_current_user),
    service: DeviceService = Depends(get_device_service),
) -> Result[DevicePageOut]:
    """按条件分页查询设备。"""
    data = await service.page(
        current_user=user,
        page=page,
        size=size,
        keyword=keyword,
        lab_id=lab_id,
        status_filter=status_filter,
    )
    return Result.ok(data)


# GET /api/devices/{device_id} 设备详情
# 学生访问停用实验室或停用设备时返回 404，视作不存在。
#
# Args:
#     device_id: 设备主键。
#     user: 当前登录用户（鉴权依赖）。
#     service: 设备业务服务（依赖注入）。
#
# Returns:
#     Result[DeviceOut]: code=200，data 为设备详情。
#
# Raises:
#     HTTPException 401: 未登录或令牌失效。
#     HTTPException 404: 设备不存在或学生无权查看。
@router.get(
    "/{device_id}",
    response_model=Result[DeviceOut],
    summary="设备详情",
    description="按 id 查询设备；学生访问停用实验室/停用设备返回 404。",
)
async def get_device(
    device_id: int,
    user: User = Depends(get_current_user),
    service: DeviceService = Depends(get_device_service),
) -> Result[DeviceOut]:
    """查询单个设备。"""
    return Result.ok(await service.get(device_id, current_user=user))


# POST /api/devices 新增设备
# 管理员创建设备；所属实验室必须存在，同一实验室内设备名唯一。
#
# Args:
#     body: 实验室 id、设备名称、型号、数量、状态、备注与排序。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 设备业务服务（依赖注入）。
#
# Returns:
#     Result[DeviceOut]: code=200，data 为创建成功的设备。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 所属实验室不存在。
#     HTTPException 409: 同一实验室下设备名重复。
#     HTTPException 422: 字段格式不合法（如数量为 0）。
@router.post(
    "",
    response_model=Result[DeviceOut],
    status_code=status.HTTP_201_CREATED,
    summary="新增设备",
    description="管理员创建设备；实验室必须存在，同一实验室内设备名唯一。",
)
async def create_device(
    body: DeviceCreateRequest,
    _: User = Depends(get_current_admin),
    service: DeviceService = Depends(get_device_service),
) -> Result[DeviceOut]:
    """创建设备。"""
    return Result.ok(await service.create(body))


# PUT /api/devices/{device_id} 编辑设备
# 只修改请求中显式提交的字段；换实验室或改名时会在目标实验室重新查重。
#
# Args:
#     device_id: 设备主键。
#     body: 待修改字段，未传的保持不变。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 设备业务服务（依赖注入）。
#
# Returns:
#     Result[DeviceOut]: code=200，data 为更新后的设备。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 设备或目标实验室不存在。
#     HTTPException 409: 目标实验室下设备名重复。
@router.put(
    "/{device_id}",
    response_model=Result[DeviceOut],
    summary="编辑设备",
    description="只提交需要变更的字段；换实验室或改名时在目标实验室重新查重。",
)
async def update_device(
    device_id: int,
    body: DeviceUpdateRequest,
    _: User = Depends(get_current_admin),
    service: DeviceService = Depends(get_device_service),
) -> Result[DeviceOut]:
    """编辑指定设备。"""
    return Result.ok(await service.update(device_id, body))


# PUT /api/devices/{device_id}/status 切换设备状态
# 正常 / 维护中 / 停用；停用后学生端列表与详情都不可见。
#
# Args:
#     device_id: 设备主键。
#     body: 目标状态 normal / maintenance / disabled。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 设备业务服务（依赖注入）。
#
# Returns:
#     Result[DeviceOut]: code=200，data 为更新后的设备。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 设备不存在。
@router.put(
    "/{device_id}/status",
    response_model=Result[DeviceOut],
    summary="切换设备状态",
    description="正常 / 维护中 / 停用；停用后学生端不可见。",
)
async def change_device_status(
    device_id: int,
    body: DeviceStatusRequest,
    _: User = Depends(get_current_admin),
    service: DeviceService = Depends(get_device_service),
) -> Result[DeviceOut]:
    """切换设备状态。"""
    return Result.ok(await service.change_status(device_id, body))


# DELETE /api/devices/{device_id} 删除设备
# 物理删除，不可恢复；预约模块落地后会补「被预约引用时拒绝删除」。
#
# Args:
#     device_id: 设备主键。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 设备业务服务（依赖注入）。
#
# Returns:
#     Result[None]: code=200，无业务数据。
#
# Raises:
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 设备不存在。
@router.delete(
    "/{device_id}",
    response_model=Result[None],
    summary="删除设备",
    description="物理删除设备；被预约引用时的保护逻辑待预约模块落地后补充。",
)
async def delete_device(
    device_id: int,
    _: User = Depends(get_current_admin),
    service: DeviceService = Depends(get_device_service),
) -> Result[None]:
    """删除指定设备。"""
    await service.delete(device_id)
    return Result.ok(None)
