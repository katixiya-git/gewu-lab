"""AI 助手的工具集（业务逻辑层，与 LangGraph 无关）。

把「查实验室 / 查设备 / 查空档 / 查我的预约 / 校验预约草稿 / 生成预约卡片」
封装成不依赖 LangGraph 的异步函数。``agent_tools.py`` 只做一层薄包装，
真正的查询与判断都在这里，好处是这些函数可以独立单测，也不绑死框架。

约定：
- 所有函数第一个参数是 ``AsyncSession``，第二类是业务参数；
- 返回纯 dict/list，字段用 camelCase，方便直接塞进模型上下文或 SSE 事件；
- **不写数据库**：``propose_booking`` 只校验并组装卡片，真正创建仍由用户点
  「确认预约」后走 ``BookingService.create``，AI 不替用户落库。

为什么要刻意「不写库」：模型会犯错，也会被提示词注入带偏。把「创建」
这个不可逆动作留给用户在卡片上点按钮，等于给 AI 加了一道人工闸门。
"""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingDevice, Device, Lab, User
from app.services.booking_rules import (
    MAX_DURATION_MINUTES,
    MIN_DURATION_MINUTES,
    duration_minutes,
    is_aligned,
    is_open_on,
    overlaps,
    within_open_hours,
)

# 仍占用时段的状态：只要不是已驳回 / 已取消，都当作占位。
# 注意 "conflict"（冲突待协调）也算占位——它还在等管理员裁决，不能当空档放出去。
ACTIVE_STATUSES = ("pending", "approved", "conflict")

# 中文标签，模型回答时直接可用（模型不必自己翻译英文枚举值，省得翻错）
CATEGORY_LABELS = {"ai": "人工智能", "robot": "机器人", "cloud": "云计算", "se": "软件工程"}
STATUS_LABELS = {"pending": "待审核", "approved": "已通过", "rejected": "已驳回", "conflict": "冲突待协调", "cancelled": "已取消"}
BOOKING_TYPE_LABELS = {"personal": "个人", "group": "小组", "class": "班级"}


def _hm(moment: time) -> str:
    """把时间格式化成 ``HH:MM``。

    模型和前端都只认 ``"14:30"`` 这种写法；Python 的 ``time`` 直接转字符串
    会带上秒（``14:30:00``），所以统一走这个函数。
    """
    return moment.strftime("%H:%M")


def _lab_brief(lab: Lab) -> dict[str, Any]:
    """实验室摘要（给模型看的最小字段集）。

    只挑模型回答需要用的字段：多余的字段既费 token，也可能让模型抓错重点。
    """
    return {
        "id": lab.id,
        "name": lab.name,
        # 把 ai/robot 这类英文枚举翻成中文，模型回答时直接能用。
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

    只返回 ``status == "enabled"`` 的：停用的实验室不该出现在 AI 的回答里，
    否则用户会被引导去一间已经关掉的房。

    Args:
        session: 数据库会话。
        keyword: 可选，按名称或位置模糊匹配。

    Returns:
        实验室摘要列表，按排序号与 id 升序。
    """
    stmt = select(Lab).where(Lab.status == "enabled").order_by(Lab.sort_order, Lab.id)
    if keyword:
        # 两边都补 %，就是 SQL 的「包含」语义；用参数化绑定而不是拼字符串，
        # ORM 会负责转义，用户输入里有引号也不会出事。
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
    # 这里 join 了实验室表：一是为了过滤掉「实验室已停用」的设备，
    # 二是顺便把实验室名字带出来，模型回答时不用再查一次。
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

    做法很朴素：拿开放时段当尺子，从开门时间起每 30 分钟切一格，
    逐格判断「有没有和已有预约重叠、是不是已经过去」，剩下没被占的格子
    就是空闲时段。为什么不直接算差集：30 分钟粒度下逐格扫描更容易读，
    数据量也小（一天最多几十格）。

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

    # 只取「还占着位」的预约来比对；已驳回/已取消的不该挡住空档。
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
    # cursor 是当前格子的起点，一路往后推；用「分钟数」比较比 time 对象好算。
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
    # 限制 20 条：模型不需要（也不该）一次读几百条，上下文有限，越少越准。
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

    分两段：先做「不查库也能判」的静态规则（开放日、粒度、时长、人数……），
    全部通过后再查一次库做重叠检测。为什么要分开：静态规则便宜，
    先挡住明显不合法的请求，能少一次全表扫描；而且错误一次收集齐，
    用户可以一次性看到所有问题，不用改一条提示一条。

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
        注意 ``errors`` 非空时 ``ok`` 为 False，但 ``conflict`` 仍可能为 False
        ——它俩是两件事：前者是「这份草稿不合法」，后者是「合法但会撞车」。
    """
    errors: list[str] = []
    lab = await session.get(Lab, lab_id)
    if lab is None or lab.status != "enabled":
        return {"ok": False, "errors": ["实验室不存在或已停用"], "conflict": False, "draft": None}

    # ---- 第一段：静态规则，错误全收集，不做短路返回 ----
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

    # ---- 设备检查：型号必须存在、属于该实验室、且没被停用 ----
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

    # ---- 第二段：只在静态规则全通过时才查重叠 ----
    # 把自己的预约和别人的分开：自己撞自己算「错误」（直接不合法），
    # 撞别人算「冲突」（可以提交，但会进入冲突待协调，由管理员裁决）。
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

    # draft 同时充当「回给模型看的摘要」和「卡片的底座」，字段用 camelCase
    # 是为了直接对齐前端 BookingCreateRequest。
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


async def propose_booking(
    session: AsyncSession,
    user_id: int,
    lab_id: int,
    booking_date: date,
    start_time: time,
    end_time: time,
    people_count: int,
    booking_type: str = "personal",
    purpose: str | None = None,
    device_ids: list[int] | None = None,
) -> dict[str, Any]:
    """生成一张「待用户确认」的预约卡片，仍然不写库。

    先按与正式创建完全相同的规则校验草稿（复用 ``validate_booking_draft``），
    通过后用当前账号补上联系人信息，拼成前端可以直接渲染的卡片。
    真正的创建发生在用户点卡片上的「确认预约」之后，由前端调用
    ``POST /api/bookings`` 完成——AI 只负责把预约准备到位，不替用户落库。

    为什么复用 ``validate_booking_draft`` 而不是各写一套：规则只有一份，
    卡片上显示「可行」的东西，点确认时一定会通过后端校验，不会出现
    「AI 说能约，点了却报错」的割裂感。

    Args:
        session: 数据库会话。
        user_id: 当前登录用户 id。
        lab_id: 实验室 id。
        booking_date: 预约日期。
        start_time: 开始时间。
        end_time: 结束时间。
        people_count: 人数。
        booking_type: 预约类型：personal / group / class，默认 personal。
        purpose: 用途说明，可空。
        device_ids: 需要的设备 id 列表。

    Returns:
        ``{"ok": bool, "errors": [...], "conflict": bool, "card": {...} | None}``；
        ``card`` 用 camelCase，字段与 ``BookingCreateRequest`` 对齐，可直接提交。
        ``conflict=True`` 表示与别人的已通过预约撞车，提交后会进入「冲突待协调」。
    """
    user = await session.get(User, user_id)
    if user is None:
        return {"ok": False, "errors": ["当前账号不存在，请重新登录"], "conflict": False, "card": None}

    checked = await validate_booking_draft(
        session,
        user_id,
        lab_id,
        booking_date,
        start_time,
        end_time,
        people_count,
        device_ids,
    )
    if not checked["ok"]:
        # 校验不过就把错误原样交回去，由模型翻译成用户能懂的话。
        return {"ok": False, "errors": checked["errors"], "conflict": False, "card": None}

    # 联系人直接取账号资料：不让模型编手机号，也不需要用户重复填写。
    phone = (user.phone or "").strip()
    if not 6 <= len(phone) <= 20:
        return {
            "ok": False,
            "errors": ["账号还没有填写联系电话，请先在个人资料里补充手机号，再来预约"],
            "conflict": False,
            "card": None,
        }

    # 模型可能传出 "Personal" 之类不合法的值，兜底回落 default，别让整轮失败。
    kind = booking_type if booking_type in BOOKING_TYPE_LABELS else "personal"
    card = {
        **checked["draft"],
        "bookingType": kind,
        "bookingTypeText": BOOKING_TYPE_LABELS[kind],
        "purpose": (purpose or "").strip()[:255],
        "contactName": user.name,
        "contactPhone": phone,
    }
    return {"ok": True, "errors": [], "conflict": checked["conflict"], "card": card}


async def search_knowledge(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """检索实验室知识库，返回带出处的片段。

    用于回答规则类问题（怎么预约、提前多久、取消限制、设备使用、安全注意事项等）。
    知识库只覆盖 `docs/knowledge/` 里的实验室文档；查无结果时不要编造。

    这一步就是 RAG（检索增强生成）的「检索」：先把问题和文档块都转成向量，
    找出最像的几块原文，塞进模型上下文——比让模型「凭记忆回答」可靠得多。

    Args:
        query: 用户的自然语言问题。
        top_k: 返回条数，默认 3。

    Returns:
        list[dict]: 每项含 docId/docTitle/section/similarity/content。
    """
    # 延迟导入：knowledge_service 会用到 AI 配置，放在函数里可以避免
    # 模块导入时就要求 Redis / API Key 齐全。
    from app.services.knowledge_service import KnowledgeService

    service = KnowledgeService()
    hits = await service.search(query, top_k=top_k)
    return [
        {
            "docId": hit.doc_id,
            "docTitle": hit.doc_title,
            "section": hit.section,
            "similarity": round(hit.similarity, 4),
            "content": hit.content,
        }
        for hit in hits
    ]


# ---------------------------------------------------------------------------
# 以下是历史遗留数据，**当前未被任何代码引用**。
#
# 早期版本直接调 OpenAI 的 function calling，需要手写这份「工具说明书」；
# 换成 LangGraph 之后，``@tool`` 会从函数签名和 docstring 自动生成同样的
# schema，这份手写副本就闲置了。留着是为了对照两边的参数差异，
# 确认不是这次改动引入的回归。要删可以直接删掉整段（不影响任何功能）。
# ---------------------------------------------------------------------------
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
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "检索实验室知识库（使用手册/预约规则/取消规则/设备说明/安全规范）。"
                "当用户问规则、流程、注意事项这类知识性问题时调用；返回带文档名与章节的片段，"
                "回答时请用 [n] 标注出处。不要把查不到的内容编造成事实。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索问题，用用户的原始问法即可"},
                    "topK": {"type": "integer", "minimum": 1, "maximum": 5, "description": "返回条数，默认 3"},
                },
                "required": ["query"],
            },
        },
    },
]
