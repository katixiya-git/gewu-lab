"""AI 助手的只读工具集。

把「查实验室 / 查设备 / 查空档 / 查我的预约 / 校验预约草稿」封装成不依赖
LangGraph 的异步函数与 OpenAI function-calling 描述，agent 图直接绑定这些工具。

约定：
- 所有函数第一个参数是 ``AsyncSession``，第二类是业务参数；
- 返回纯 dict/list，字段用 camelCase，方便直接塞进模型上下文或 SSE 事件；
- 不写数据库：创建预约仍走 ``BookingService.create``，这里只做校验与草稿。
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingDevice, Device, Lab
from app.services.booking_rules import (
    MAX_DURATION_MINUTES,
    MIN_DURATION_MINUTES,
    duration_minutes,
    is_aligned,
    is_open_on,
    overlaps,
    within_open_hours,
)

# 仍占用时段的状态：只要不是已驳回 / 已取消，都当作占位
ACTIVE_STATUSES = ("pending", "approved", "conflict")

# 中文标签，模型回答时直接可用
CATEGORY_LABELS = {"ai": "人工智能", "robot": "机器人", "cloud": "云计算", "se": "软件工程"}
STATUS_LABELS = {"pending": "待审核", "approved": "已通过", "rejected": "已驳回", "conflict": "冲突待协调", "cancelled": "已取消"}


def _hm(moment: time) -> str:
    """把时间格式化成 ``HH:MM``。"""
    return moment.strftime("%H:%M")


def _lab_brief(lab: Lab) -> dict[str, Any]:
    """实验室摘要（给模型看的最小字段集）。"""
    return {
        "id": lab.id,
        "name": lab.name,
        "category": CATEGORY_LABELS.get(lab.category, lab.category),
        "location": lab.location,
        "capacity": lab.capacity,
        "openDays": lab.open_days,
        "openTime": _hm(lab.open_time),
        "closeTime": _hm(lab.close_time),
        "rule": lab.rule or "",
        "description": lab.description or "",
    }


def _device_brief(device: Device) -> dict[str, Any]:
    """设备摘要。"""
    return {
        "id": device.id,
        "labId": device.lab_id,
        "name": device.name,
        "model": device.model or "",
        "count": device.total_count,
        "status": device.status,
        "note": device.note or "",
    }


async def list_labs(session: AsyncSession, keyword: str | None = None) -> list[dict[str, Any]]:
    """查询开放中的实验室列表。

    Args:
        session: 数据库会话。
        keyword: 可选，按名称或位置模糊匹配。

    Returns:
        实验室摘要列表，按排序号与 id 升序。
    """
    stmt = select(Lab).where(Lab.status == "enabled").order_by(Lab.sort_order, Lab.id)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(or_(Lab.name.like(like), Lab.location.like(like)))
    labs = (await session.execute(stmt)).scalars().all()
    return [_lab_brief(lab) for lab in labs]


async def get_lab(session: AsyncSession, lab_id: int) -> dict[str, Any] | None:
    """查询单个实验室详情（含设备清单）。

    Args:
        session: 数据库会话。
        lab_id: 实验室 id。

    Returns:
        实验室详情；不存在或已停用时返回 ``None``。
    """
    lab = await session.get(Lab, lab_id)
    if lab is None or lab.status != "enabled":
        return None
    devices = (
        await session.execute(
            select(Device).where(Device.lab_id == lab_id, Device.status != "disabled").order_by(Device.sort_order, Device.id)
        )
    ).scalars().all()
    detail = _lab_brief(lab)
    detail["devices"] = [_device_brief(device) for device in devices]
    return detail


async def list_devices(session: AsyncSession, lab_id: int | None = None) -> list[dict[str, Any]]:
    """查询设备清单。

    Args:
        session: 数据库会话。
        lab_id: 可选，限定某个实验室。

    Returns:
        设备摘要列表（停用设备不返回）。
    """
    stmt = (
        select(Device, Lab.name)
        .join(Lab, Lab.id == Device.lab_id)
        .where(Device.status != "disabled", Lab.status == "enabled")
        .order_by(Device.lab_id, Device.sort_order, Device.id)
    )
    if lab_id is not None:
        stmt = stmt.where(Device.lab_id == lab_id)
    rows = (await session.execute(stmt)).all()
    return [{**_device_brief(device), "labName": lab_name} for device, lab_name in rows]


async def find_free_slots(session: AsyncSession, lab_id: int, day: date) -> dict[str, Any]:
    """查询某实验室某天的空闲时段。

    Args:
        session: 数据库会话。
        lab_id: 实验室 id。
        day: 目标日期。

    Returns:
        ``{"date","open","reason","slots":[{"start","end"}]}``：``slots`` 是 30 分钟
        粒度的空闲起点，按时间升序；``open=False`` 时 ``reason`` 说明原因。
    """
    lab = await session.get(Lab, lab_id)
    if lab is None or lab.status != "enabled":
        return {"date": day.isoformat(), "open": False, "reason": "实验室不存在或已停用", "slots": []}
    if not is_open_on(lab.open_days, day):
        return {"date": day.isoformat(), "open": False, "reason": "当天不是该实验室的开放日", "slots": []}
    if day < date.today():
        return {"date": day.isoformat(), "open": False, "reason": "日期已过去", "slots": []}

    booked = (
        await session.execute(
            select(Booking).where(
                Booking.lab_id == lab_id,
                Booking.booking_date == day,
                Booking.status.in_(ACTIVE_STATUSES),
            )
        )
    ).scalars().all()

    now = datetime.now()
    slots: list[dict[str, str]] = []
    cursor = lab.open_time
    close_minutes = lab.close_time.hour * 60 + lab.close_time.minute
    while cursor.hour * 60 + cursor.minute + 30 <= close_minutes:
        start_minutes = cursor.hour * 60 + cursor.minute
        end = time((start_minutes + 30) // 60, (start_minutes + 30) % 60)
        busy = any(overlaps(cursor, end, booking.start_time, booking.end_time) for booking in booked)
        # 今天的日期，只保留还没结束的时段
        if not busy and (day > now.date() or end > now.time()):
            slots.append({"start": _hm(cursor), "end": _hm(end)})
        cursor = end

    return {"date": day.isoformat(), "open": True, "reason": "", "slots": slots}


async def list_my_bookings(session: AsyncSession, user_id: int, status: str | None = None) -> list[dict[str, Any]]:
    """查询某个学生自己的预约。

    Args:
        session: 数据库会话。
        user_id: 学生用户 id。
        status: 可选状态过滤（pending/approved/rejected/conflict/cancelled）。

    Returns:
        预约摘要列表，按日期倒序。
    """
    stmt = (
        select(Booking, Lab.name)
        .join(Lab, Lab.id == Booking.lab_id)
        .where(Booking.user_id == user_id)
        .order_by(Booking.booking_date.desc(), Booking.start_time.desc(), Booking.id.desc())
        .limit(20)
    )
    if status:
        stmt = stmt.where(Booking.status == status)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "code": booking.code,
            "labName": lab_name,
            "date": booking.booking_date.isoformat(),
            "start": _hm(booking.start_time),
            "end": _hm(booking.end_time),
            "peopleCount": booking.people_count,
            "bookingType": booking.booking_type,
            "status": booking.status,
            "statusText": STATUS_LABELS.get(booking.status, booking.status),
            "rejectReason": booking.reject_reason or "",
            "cancelRequested": bool(booking.cancel_requested),
        }
        for booking, lab_name in rows
    ]


async def validate_booking_draft(
    session: AsyncSession,
    user_id: int,
    lab_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    people_count: int,
    device_ids: list[int] | None = None,
) -> dict[str, Any]:
    """校验一份预约草稿（不写库），返回是否可行与原因。

    Args:
        session: 数据库会话。
        user_id: 学生用户 id。
        lab_id: 实验室 id。
        booking_date: 预约日期。
        start_time: 开始时间。
        end_time: 结束时间。
        people_count: 人数。
        device_ids: 需要的设备 id 列表。

    Returns:
        ``{"ok": bool, "errors": [...], "conflict": bool, "draft": {...}}``；
        ``conflict=True`` 表示与其他学生的已通过预约撞车，需要管理员协调。
    """
    errors: list[str] = []
    lab = await session.get(Lab, lab_id)
    if lab is None or lab.status != "enabled":
        return {"ok": False, "errors": ["实验室不存在或已停用"], "conflict": False, "draft": None}

    if not is_open_on(lab.open_days, booking_date):
        errors.append("该日期不是实验室开放日")
    if not is_aligned(start_time) or not is_aligned(end_time):
        errors.append("开始和结束时间必须按 30 分钟对齐")
    minutes = duration_minutes(start_time, end_time)
    if minutes < MIN_DURATION_MINUTES or minutes > MAX_DURATION_MINUTES:
        errors.append("单次预约时长需在 30 分钟到 4 小时之间")
    if not within_open_hours(start_time, end_time, lab.open_time, lab.close_time):
        errors.append(f"预约需在开放时段 {_hm(lab.open_time)}–{_hm(lab.close_time)} 内")
    if people_count < 1 or people_count > lab.capacity:
        errors.append(f"人数需在 1–{lab.capacity} 之间")
    if booking_date < date.today():
        errors.append("不能预约过去的日期")

    devices: list[Device] = []
    if device_ids:
        devices = (
            await session.execute(select(Device).where(Device.id.in_(device_ids)))
        ).scalars().all()
        found = {device.id for device in devices}
        for device_id in device_ids:
            if device_id not in found:
                errors.append(f"设备不存在：id={device_id}")
        for device in devices:
            if device.lab_id != lab_id:
                errors.append(f"设备「{device.name}」不属于该实验室")
            if device.status == "disabled":
                errors.append(f"设备「{device.name}」已停用")

    conflict = False
    if not errors:
        active = (
            await session.execute(
                select(Booking).where(
                    Booking.lab_id == lab_id,
                    Booking.booking_date == booking_date,
                    Booking.status.in_(ACTIVE_STATUSES),
                )
            )
        ).scalars().all()
        mine = [booking for booking in active if booking.user_id == user_id]
        others = [booking for booking in active if booking.user_id != user_id]
        if any(overlaps(start_time, end_time, booking.start_time, booking.end_time) for booking in mine):
            errors.append("你在这个时段已有预约")
        conflict = any(overlaps(start_time, end_time, booking.start_time, booking.end_time) for booking in others)

    draft = {
        "labId": lab.id,
        "labName": lab.name,
        "bookingDate": booking_date.isoformat(),
        "startTime": _hm(start_time),
        "endTime": _hm(end_time),
        "peopleCount": people_count,
        "deviceIds": list(device_ids or []),
        "deviceNames": [device.name for device in devices],
    }
    return {"ok": not errors, "errors": errors, "conflict": conflict, "draft": draft}


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_labs",
            "description": "查询开放中的实验室列表（名称、位置、容量、开放日与时段、使用规则）。",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "可选，按名称或位置模糊搜索"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lab",
            "description": "查询单个实验室详情，包含设备清单。",
            "parameters": {
                "type": "object",
                "properties": {"labId": {"type": "integer", "description": "实验室 id"}},
                "required": ["labId"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "查询设备清单，可按实验室过滤。",
            "parameters": {
                "type": "object",
                "properties": {"labId": {"type": "integer", "description": "可选，实验室 id"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_free_slots",
            "description": "查询某实验室某天的空闲时段（30 分钟粒度）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "labId": {"type": "integer", "description": "实验室 id"},
                    "date": {"type": "string", "description": "日期，格式 YYYY-MM-DD"},
                },
                "required": ["labId", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_bookings",
            "description": "查询当前学生自己的预约记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "approved", "rejected", "conflict", "cancelled"]}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_booking_draft",
            "description": "校验一份预约草稿是否可行（不创建预约），返回错误或冲突提示。",
            "parameters": {
                "type": "object",
                "properties": {
                    "labId": {"type": "integer"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "startTime": {"type": "string", "description": "HH:MM"},
                    "endTime": {"type": "string", "description": "HH:MM"},
                    "peopleCount": {"type": "integer"},
                    "deviceIds": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["labId", "date", "startTime", "endTime", "peopleCount"],
            },
        },
    },
]
