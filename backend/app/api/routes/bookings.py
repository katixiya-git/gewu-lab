"""预约接口：只做参数接收、鉴权与响应封装。

业务实现在 ``app.services.booking_service.BookingService``。学生只能操作
自己的预约；审核与取消申请处理仅管理员可用。
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_booking_service, get_current_admin, get_current_user
from app.core.result import Result
from app.models import User
from app.schemas import (
    BookingCancelRequest,
    BookingCancelReviewRequest,
    BookingCreateRequest,
    BookingOut,
    BookingPageOut,
    BookingReviewRequest,
)
from app.services import BookingService

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


# GET /api/bookings/page 分页查询预约
# 学生强制只看自己的；管理员可看全部，并按状态/实验室/关键字/日期区间筛选。
# 关键字匹配预约号、用途、联系人、电话、实验室名与学生姓名。
#
# Args:
#     page: 页码，从 1 开始。
#     size: 每页条数，1–50。
#     status_filter: 可选状态过滤：pending / approved / rejected / conflict / cancelled。
#     lab_id: 可选实验室过滤。
#     keyword: 可选关键字，最长 50 字符。
#     date_from: 预约日期下限（含）。
#     date_to: 预约日期上限（含）。
#     user: 当前登录用户（鉴权依赖）。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingPageOut]: code=200，data 含 total 与 items。
#
# Raises:
#     HTTPException 401: 未登录或令牌失效。
@router.get(
    "/page",
    response_model=Result[BookingPageOut],
    summary="分页查询预约",
    description="学生只能看到自己的预约；管理员可看全部并按状态、实验室、日期筛选。",
)
async def page_bookings(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(10, ge=1, le=50, description="每页条数"),
    status_filter: str | None = Query(
        None,
        alias="status",
        description="按状态过滤：pending / approved / rejected / conflict / cancelled",
    ),
    lab_id: int | None = Query(None, alias="labId", ge=1, description="按实验室过滤"),
    keyword: str | None = Query(None, max_length=50, description="预约号/用途/联系人/实验室/学生姓名"),
    date_from: date | None = Query(None, alias="dateFrom", description="预约日期下限（含）"),
    date_to: date | None = Query(None, alias="dateTo", description="预约日期上限（含）"),
    user: User = Depends(get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingPageOut]:
    """按条件分页查询预约。"""
    data = await service.page(
        current_user=user,
        page=page,
        size=size,
        status_filter=status_filter,
        lab_id=lab_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )
    return Result.ok(data)


# GET /api/bookings/{booking_id} 预约详情
# 学生访问别人的预约返回 404，不暴露预约是否存在。
#
# Args:
#     booking_id: 预约主键。
#     user: 当前登录用户（鉴权依赖）。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingOut]: code=200，data 为预约详情。
#
# Raises:
#     HTTPException 401: 未登录或令牌失效。
#     HTTPException 404: 预约不存在或不属于当前学生。
@router.get(
    "/{booking_id}",
    response_model=Result[BookingOut],
    summary="预约详情",
    description="学生只能查看自己的预约；访问别人的预约返回 404。",
)
async def get_booking(
    booking_id: int,
    user: User = Depends(get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingOut]:
    """查询单条预约。"""
    return Result.ok(await service.get(booking_id, current_user=user))


# POST /api/bookings 提交预约
# 学生/管理员都可以提交。服务层按顺序校验：实验室启用、日期与开放日、
# 时段对齐与时长、开放时间、人数、设备归属、本人时段重叠，最后判定
# pending 还是 conflict（撞已有 approved）。
#
# Args:
#     body: 实验室、日期、起止时间、人数、类型、用途、联系人、设备。
#     user: 当前登录用户（鉴权依赖）。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingOut]: code=200，data 为新建预约（status 可能是 conflict）。
#
# Raises:
#     HTTPException 400: 日期/时段/人数/设备等业务校验失败。
#     HTTPException 404: 实验室不存在。
#     HTTPException 409: 本人在该时段已有预约。
@router.post(
    "",
    response_model=Result[BookingOut],
    status_code=status.HTTP_201_CREATED,
    summary="提交预约",
    description="校验实验室、开放时间、人数与设备；与已通过预约重叠时落为 conflict。",
)
async def create_booking(
    body: BookingCreateRequest,
    user: User = Depends(get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingOut]:
    """提交一条预约。"""
    return Result.ok(await service.create(body, current_user=user))


# POST /api/bookings/{booking_id}/review 审核预约
# 管理员通过或驳回 pending / conflict 的预约；通过前会再查一次同时段
# 是否已有 approved，驳回必须写理由。
#
# Args:
#     booking_id: 预约主键。
#     body: action=approve|reject，驳回时 reason 必填。
#     _: 管理员鉴权依赖，学生调用返回 403。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingOut]: code=200，data 为审核后的预约。
#
# Raises:
#     HTTPException 400: 当前状态不可审核，或驳回没写理由。
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 预约不存在。
#     HTTPException 409: 该时段已有通过的预约。
@router.post(
    "/{booking_id}/review",
    response_model=Result[BookingOut],
    summary="审核预约",
    description="管理员通过或驳回；通过时禁止与已通过预约重叠，驳回必须填理由。",
)
async def review_booking(
    booking_id: int,
    body: BookingReviewRequest,
    admin: User = Depends(get_current_admin),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingOut]:
    """审核指定预约。"""
    return Result.ok(await service.review(booking_id, body, current_user=admin))


# POST /api/bookings/{booking_id}/cancel 直接取消预约
# 本人或管理员可取消；已驳回/已取消不能再取消。学生的 approved 预约
# 距开始不足 12 小时时会被要求改走「提交取消申请」。
#
# Args:
#     booking_id: 预约主键。
#     body: 可选取消理由。
#     user: 当前登录用户（鉴权依赖）。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingOut]: code=200，data 为已取消的预约。
#
# Raises:
#     HTTPException 400: 状态不允许取消，或 12 小时内需走申请。
#     HTTPException 401: 未登录或令牌失效。
#     HTTPException 404: 预约不存在或不属于当前学生。
@router.post(
    "/{booking_id}/cancel",
    response_model=Result[BookingOut],
    summary="取消预约",
    description="12 小时外或未通过的预约可直接取消；12 小时内需提交取消申请。",
)
async def cancel_booking(
    booking_id: int,
    body: BookingCancelRequest,
    user: User = Depends(get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingOut]:
    """取消指定预约。"""
    return Result.ok(await service.cancel(booking_id, body, current_user=user))


# POST /api/bookings/{booking_id}/cancel-request 提交取消申请
# 仅本人、仅 approved 且距开始不足 12 小时可提交；重复提交返回 400。
#
# Args:
#     booking_id: 预约主键。
#     body: 可选申请理由。
#     user: 当前登录用户（鉴权依赖）。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingOut]: code=200，cancelRequested=true。
#
# Raises:
#     HTTPException 400: 非 approved、已申请过，或距开始仍超过 12 小时。
#     HTTPException 404: 预约不存在或不属于当前学生。
@router.post(
    "/{booking_id}/cancel-request",
    response_model=Result[BookingOut],
    summary="提交取消申请",
    description="距开始不足 12 小时的已通过预约，由学生提交取消申请。",
)
async def request_cancel_booking(
    booking_id: int,
    body: BookingCancelRequest,
    user: User = Depends(get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingOut]:
    """学生提交取消申请。"""
    return Result.ok(await service.request_cancel(booking_id, body, current_user=user))


# POST /api/bookings/{booking_id}/cancel-review 处理取消申请
# 管理员同意则预约变为 cancelled；拒绝则清掉 cancelRequested 并记录说明。
#
# Args:
#     booking_id: 预约主键。
#     body: approve=true/false，可选说明。
#     admin: 管理员鉴权依赖，学生调用返回 403。
#     service: 预约业务服务（依赖注入）。
#
# Returns:
#     Result[BookingOut]: code=200，data 为处理后的预约。
#
# Raises:
#     HTTPException 400: 该预约没有待处理的取消申请。
#     HTTPException 403: 当前账号不是管理员。
#     HTTPException 404: 预约不存在。
@router.post(
    "/{booking_id}/cancel-review",
    response_model=Result[BookingOut],
    summary="处理取消申请",
    description="管理员同意则取消预约，拒绝则保留并记录说明。",
)
async def review_cancel_booking(
    booking_id: int,
    body: BookingCancelReviewRequest,
    admin: User = Depends(get_current_admin),
    service: BookingService = Depends(get_booking_service),
) -> Result[BookingOut]:
    """管理员处理学生的取消申请。"""
    return Result.ok(await service.review_cancel(booking_id, body, current_user=admin))
