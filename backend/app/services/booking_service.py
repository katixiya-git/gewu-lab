"""预约业务服务：提交、查询、审核、取消与冲突处理。

本模块只处理业务规则与数据读写，不感知 HTTP 路由；接口层见
``app.api.routes.bookings``。时间计算全部走 ``booking_rules`` 里的纯函数。

状态机（详见计划文档）：

    pending ──通过──► approved ──12h 外取消──► cancelled
       │                 └─12h 内申请取消──► approved(cancel_requested)
       ├─驳回──► rejected
       └─撞 approved──► conflict

- 提交时如果同实验室同时段已有 approved，直接落 ``conflict``；
- 审核通过前再查一次重叠，保证不会出现两张 approved 重叠；
- approved 被取消后，同实验室同时段因此产生的 ``conflict`` 单自动退回 ``pending``。
"""

from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Booking, BookingDevice, Device, Lab, User
from app.schemas.booking import (
    BookingCancelRequest,
    BookingCancelReviewRequest,
    BookingCreateRequest,
    BookingDeviceOut,
    BookingOut,
    BookingPageOut,
    BookingReviewRequest,
)
from app.services import booking_rules

# 取消规则：距开始不足 12 小时只能提交申请
CANCEL_FREE_HOURS = 12

# 这些状态算「还占着时段」，用于判断申请人自己的重叠
ACTIVE_STATUSES = ("pending", "approved", "conflict")


class BookingService:
    """预约业务的统一入口。"""

    def __init__(self, session: AsyncSession) -> None:
        """Args:
            session: 由接口层依赖注入的异步数据库会话。
        """
        self.session = session

    # ------------------------------------------------------------------ 查询

    async def page(
        self,
        *,
        current_user: User,
        page: int,
        size: int,
        status_filter: str | None,
        lab_id: int | None,
        keyword: str | None,
        date_from: date | None,
        date_to: date | None,
    ) -> BookingPageOut:
        """按条件分页查询预约。

        学生强制只看自己的；管理员可看全部，并按状态 / 实验室 / 关键字 /
        日期区间筛选。关键字匹配预约号、用途、联系人、电话、实验室名、学生姓名。

        Args:
            current_user: 当前登录用户。
            page: 页码，从 1 开始。
            size: 每页条数。
            status_filter: 可选状态过滤。
            lab_id: 可选实验室过滤。
            keyword: 可选关键字。
            date_from: 预约日期下限（含）。
            date_to: 预约日期上限（含）。

        Returns:
            BookingPageOut: 总条数与当前页预约。
        """
        conditions = []

        if current_user.role != "admin":
            conditions.append(Booking.user_id == current_user.id)

        if status_filter in ("pending", "approved", "rejected", "conflict", "cancelled"):
            conditions.append(Booking.status == status_filter)

        if lab_id:
            conditions.append(Booking.lab_id == lab_id)

        if date_from:
            conditions.append(Booking.booking_date >= date_from)
        if date_to:
            conditions.append(Booking.booking_date <= date_to)

        if keyword and keyword.strip():
            like = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    Booking.code.like(like),
                    Booking.purpose.like(like),
                    Booking.contact_name.like(like),
                    Booking.contact_phone.like(like),
                    Lab.name.like(like),
                    User.name.like(like),
                )
            )

        base = (
            select(Booking, User.name, Lab.name)
            .join(User, User.id == Booking.user_id)
            .join(Lab, Lab.id == Booking.lab_id)
            .where(*conditions)
        )

        total = await self.session.scalar(
            select(func.count())
            .select_from(Booking)
            .join(User, User.id == Booking.user_id)
            .join(Lab, Lab.id == Booking.lab_id)
            .where(*conditions)
        )

        rows = (
            await self.session.execute(
                base.order_by(Booking.booking_date.desc(), Booking.start_time.desc(), Booking.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()

        items = await self._build_out_list(rows)
        return BookingPageOut(total=total or 0, items=items)

    async def get(self, booking_id: int, *, current_user: User) -> BookingOut:
        """按 id 查询预约详情。

        学生访问别人的预约返回 404（不暴露是否存在）。

        Args:
            booking_id: 预约 id。
            current_user: 当前登录用户。

        Returns:
            BookingOut: 预约详情。

        Raises:
            HTTPException 404: 预约不存在，或不属于当前学生。
        """
        booking = await self._get_or_404(booking_id)
        if current_user.role != "admin" and booking.user_id != current_user.id:
            raise self._not_found()
        return (await self._build_out_list([(booking, await self._user_name(booking.user_id), await self._lab_name(booking.lab_id))]))[0]

    # ------------------------------------------------------------------ 提交

    async def create(self, payload: BookingCreateRequest, *, current_user: User) -> BookingOut:
        """提交一条预约。

        校验顺序：实验室可用 → 日期/时段合法 → 人数 → 设备 → 本人重叠 →
        判定 pending / conflict。任何一项不满足都直接抛错，不落库。

        Args:
            payload: 提交入参。
            current_user: 申请人。

        Returns:
            BookingOut: 新建的预约（可能是 conflict）。

        Raises:
            HTTPException 404: 实验室不存在。
            HTTPException 400: 日期、时段、人数或设备不合法。
            HTTPException 409: 本人在该时段已有预约。
        """
        lab = await self._get_lab_or_404(payload.lab_id)
        if lab.status != "enabled":
            raise HTTPException(status_code=400, detail="实验室已停用，暂不可预约")

        self._validate_time_window(payload, lab)

        if payload.people_count > lab.capacity:
            raise HTTPException(status_code=400, detail=f"人数超过实验室容量（{lab.capacity} 人）")

        devices = await self._resolve_devices(payload.device_ids, lab.id)

        await self._ensure_no_self_overlap(current_user.id, payload)

        status_value = "conflict" if await self._has_approved_overlap(
            lab_id=lab.id,
            booking_date=payload.booking_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
        ) else "pending"

        booking = Booking(
            code=await self._next_code(),
            user_id=current_user.id,
            lab_id=lab.id,
            booking_date=payload.booking_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            people_count=payload.people_count,
            booking_type=payload.booking_type,
            purpose=payload.purpose,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            status=status_value,
        )
        self.session.add(booking)
        try:
            await self.session.flush()
            for device in devices:
                self.session.add(BookingDevice(booking_id=booking.id, device_id=device.id))
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="预约号冲突，请重试") from exc

        await self.session.refresh(booking)
        return (await self._build_out_list([(booking, current_user.name, lab.name)]))[0]

    # ------------------------------------------------------------------ 审核

    async def review(
        self,
        booking_id: int,
        payload: BookingReviewRequest,
        *,
        current_user: User,
    ) -> BookingOut:
        """管理员审核预约：通过或驳回。

        通过前会再查一次同时段是否有别的 approved，避免两张通过的预约重叠；
        驳回必须带理由。

        Args:
            booking_id: 预约 id。
            payload: 审核动作与理由。
            current_user: 审核人（管理员）。

        Returns:
            BookingOut: 审核后的预约。

        Raises:
            HTTPException 404: 预约不存在。
            HTTPException 400: 当前状态不可审核，或驳回缺少理由。
            HTTPException 409: 该时段已有通过的预约。
        """
        booking = await self._get_or_404(booking_id)
        if booking.status not in ("pending", "conflict"):
            raise HTTPException(status_code=400, detail="当前状态不可审核")

        now = datetime.now()

        if payload.action == "reject":
            reason = (payload.reason or "").strip()
            if not reason:
                raise HTTPException(status_code=400, detail="驳回预约必须填写理由")
            booking.status = "rejected"
            booking.reject_reason = reason
            booking.reviewer_id = current_user.id
            booking.reviewed_at = now
            await self.session.commit()
        else:
            if await self._has_approved_overlap(
                lab_id=booking.lab_id,
                booking_date=booking.booking_date,
                start_time=booking.start_time,
                end_time=booking.end_time,
                exclude_id=booking.id,
            ):
                raise HTTPException(status_code=409, detail="该时段已有通过的预约，请先协调")
            booking.status = "approved"
            booking.reviewer_id = current_user.id
            booking.reviewed_at = now
            await self.session.commit()

        await self.session.refresh(booking)
        return (await self._build_out_list([(booking, await self._user_name(booking.user_id), await self._lab_name(booking.lab_id))]))[0]

    # ------------------------------------------------------------------ 取消

    async def cancel(
        self,
        booking_id: int,
        payload: BookingCancelRequest,
        *,
        current_user: User,
    ) -> BookingOut:
        """直接取消预约。

        本人或管理员可取消；已驳回 / 已取消的不能再取消。学生的已通过预约
        如果距开始不足 12 小时，会被要求改走「取消申请」。

        Args:
            booking_id: 预约 id。
            payload: 取消理由（可选）。
            current_user: 当前登录用户。

        Returns:
            BookingOut: 取消后的预约。

        Raises:
            HTTPException 404: 预约不存在或不属于当前学生。
            HTTPException 400: 状态不允许取消，或 12 小时内需走申请。
        """
        booking = await self._get_or_404(booking_id)
        self._ensure_can_operate(booking, current_user)

        if booking.status in ("rejected", "cancelled"):
            raise HTTPException(status_code=400, detail="该预约已结束，无需取消")

        if booking.status == "approved" and current_user.role != "admin":
            hours = booking_rules.hours_until(booking.booking_date, booking.start_time, datetime.now())
            if hours < CANCEL_FREE_HOURS:
                raise HTTPException(
                    status_code=400,
                    detail="距开始不足 12 小时，请提交取消申请，由管理员处理",
                )

        was_approved = booking.status == "approved"
        booking.status = "cancelled"
        booking.cancel_requested = False
        booking.cancel_reason = (payload.reason or booking.cancel_reason or "").strip() or None
        await self.session.commit()
        await self.session.refresh(booking)

        if was_approved:
            await self._release_conflicts(booking)

        return (await self._build_out_list([(booking, await self._user_name(booking.user_id), await self._lab_name(booking.lab_id))]))[0]

    async def request_cancel(
        self,
        booking_id: int,
        payload: BookingCancelRequest,
        *,
        current_user: User,
    ) -> BookingOut:
        """学生在 12 小时内提交取消申请。

        Args:
            booking_id: 预约 id。
            payload: 申请理由（可选，但建议填）。
            current_user: 申请人。

        Returns:
            BookingOut: 标记了 ``cancel_requested`` 的预约。

        Raises:
            HTTPException 404: 预约不存在或不属于当前学生。
            HTTPException 400: 不是已通过状态、已经申请过，或距开始仍超过 12 小时。
        """
        booking = await self._get_or_404(booking_id)
        if booking.user_id != current_user.id:
            raise self._not_found()

        if booking.status != "approved":
            raise HTTPException(status_code=400, detail="只有已通过的预约才能申请取消")
        if booking.cancel_requested:
            raise HTTPException(status_code=400, detail="已提交过取消申请，请等待管理员处理")

        hours = booking_rules.hours_until(booking.booking_date, booking.start_time, datetime.now())
        if hours >= CANCEL_FREE_HOURS:
            raise HTTPException(status_code=400, detail="距开始超过 12 小时，可以直接取消")

        booking.cancel_requested = True
        booking.cancel_reason = (payload.reason or "").strip() or None
        await self.session.commit()
        await self.session.refresh(booking)
        return (await self._build_out_list([(booking, await self._user_name(booking.user_id), await self._lab_name(booking.lab_id))]))[0]

    async def review_cancel(
        self,
        booking_id: int,
        payload: BookingCancelReviewRequest,
        *,
        current_user: User,
    ) -> BookingOut:
        """管理员处理学生的取消申请：同意则取消，拒绝则保留并写说明。

        Args:
            booking_id: 预约 id。
            payload: 是否同意与理由。
            current_user: 管理员。

        Returns:
            BookingOut: 处理后的预约。

        Raises:
            HTTPException 404: 预约不存在。
            HTTPException 400: 当前预约没有待处理的取消申请。
        """
        booking = await self._get_or_404(booking_id)
        if booking.status != "approved" or not booking.cancel_requested:
            raise HTTPException(status_code=400, detail="该预约没有待处理的取消申请")

        reason = (payload.reason or "").strip()

        if payload.approve:
            booking.status = "cancelled"
            booking.cancel_requested = False
            booking.reviewer_id = current_user.id
            booking.reviewed_at = datetime.now()
            await self.session.commit()
            await self.session.refresh(booking)
            await self._release_conflicts(booking)
        else:
            booking.cancel_requested = False
            booking.reject_reason = f"取消申请未通过：{reason}" if reason else "取消申请未通过"
            await self.session.commit()
            await self.session.refresh(booking)

        return (await self._build_out_list([(booking, await self._user_name(booking.user_id), await self._lab_name(booking.lab_id))]))[0]

    # ------------------------------------------------------------------ 规则

    def _validate_time_window(self, payload: BookingCreateRequest, lab: Lab) -> None:
        """校验日期在开放日、时段在开放时间内、30 分钟对齐、时长 30 分钟–4 小时。"""
        today = date.today()
        if payload.booking_date < today:
            raise HTTPException(status_code=400, detail="不能预约过去的日期")

        if not booking_rules.is_open_on(lab.open_days, payload.booking_date):
            raise HTTPException(status_code=400, detail="该实验室当天不开放")

        if payload.start_time >= payload.end_time:
            raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

        if not booking_rules.is_aligned(payload.start_time) or not booking_rules.is_aligned(payload.end_time):
            raise HTTPException(status_code=400, detail="预约时间需按 30 分钟对齐")

        minutes = booking_rules.duration_minutes(payload.start_time, payload.end_time)
        if not (booking_rules.MIN_DURATION_MINUTES <= minutes <= booking_rules.MAX_DURATION_MINUTES):
            raise HTTPException(status_code=400, detail="单次预约时长需在 30 分钟到 4 小时之间")

        if not booking_rules.within_open_hours(
            payload.start_time, payload.end_time, lab.open_time, lab.close_time
        ):
            raise HTTPException(status_code=400, detail="预约时段超出实验室开放时间")

        if payload.booking_date == today:
            now_time = datetime.now().time()
            if payload.start_time <= now_time:
                raise HTTPException(status_code=400, detail="该时段已经开始，请选择更晚的时间")

    async def _resolve_devices(self, device_ids: list[int], lab_id: int) -> list[Device]:
        """校验设备都属于该实验室且未停用，并返回 ORM 列表（去重保序）。"""
        unique_ids = list(dict.fromkeys(device_ids))
        if not unique_ids:
            return []

        devices = (
            await self.session.scalars(select(Device).where(Device.id.in_(unique_ids)))
        ).all()
        found = {device.id: device for device in devices}

        for device_id in unique_ids:
            device = found.get(device_id)
            if device is None:
                raise HTTPException(status_code=400, detail=f"设备不存在：id={device_id}")
            if device.lab_id != lab_id:
                raise HTTPException(status_code=400, detail="所选设备不属于该实验室")
            if device.status == "disabled":
                raise HTTPException(status_code=400, detail=f"设备已停用：{device.name}")

        return [found[device_id] for device_id in unique_ids]

    async def _ensure_no_self_overlap(self, user_id: int, payload: BookingCreateRequest) -> None:
        """同一个人在同一天、同一时段不能有两张还没结束的预约。"""
        conflict_count = await self.session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.user_id == user_id,
                Booking.booking_date == payload.booking_date,
                Booking.status.in_(ACTIVE_STATUSES),
                Booking.start_time < payload.end_time,
                Booking.end_time > payload.start_time,
            )
        )
        if conflict_count:
            raise HTTPException(status_code=409, detail="你在这个时段已有预约")

    async def _has_approved_overlap(
        self,
        *,
        lab_id: int,
        booking_date: date,
        start_time,
        end_time,
        exclude_id: int | None = None,
    ) -> bool:
        """同实验室、同日期、时段重叠的 approved 数量是否大于 0。"""
        conditions = [
            Booking.lab_id == lab_id,
            Booking.booking_date == booking_date,
            Booking.status == "approved",
            Booking.start_time < end_time,
            Booking.end_time > start_time,
        ]
        if exclude_id is not None:
            conditions.append(Booking.id != exclude_id)

        count = await self.session.scalar(select(func.count()).select_from(Booking).where(*conditions))
        return bool(count)

    async def _release_conflicts(self, cancelled: Booking) -> None:
        """已通过的预约被取消后，把因此产生、且不再冲突的 conflict 单退回 pending。"""
        conflicts = (
            await self.session.scalars(
                select(Booking).where(
                    Booking.lab_id == cancelled.lab_id,
                    Booking.booking_date == cancelled.booking_date,
                    Booking.status == "conflict",
                    Booking.start_time < cancelled.end_time,
                    Booking.end_time > cancelled.start_time,
                )
            )
        ).all()

        for item in conflicts:
            still_blocked = await self._has_approved_overlap(
                lab_id=item.lab_id,
                booking_date=item.booking_date,
                start_time=item.start_time,
                end_time=item.end_time,
                exclude_id=item.id,
            )
            if not still_blocked:
                item.status = "pending"

        if conflicts:
            await self.session.commit()

    # ------------------------------------------------------------------ 工具

    async def _get_or_404(self, booking_id: int) -> Booking:
        """按 id 取预约，不存在抛 404。"""
        booking = await self.session.get(Booking, booking_id)
        if booking is None:
            raise self._not_found()
        return booking

    async def _get_lab_or_404(self, lab_id: int) -> Lab:
        """按 id 取实验室，不存在抛 404。"""
        lab = await self.session.get(Lab, lab_id)
        if lab is None:
            raise HTTPException(status_code=404, detail="实验室不存在")
        return lab

    async def _next_code(self) -> str:
        """生成 ``BKyyyymmddNNNN`` 预约号（按当天已有最大序号 +1）。"""
        prefix = f"BK{date.today():%Y%m%d}"
        latest = await self.session.scalar(
            select(func.max(Booking.code)).where(Booking.code.like(f"{prefix}%"))
        )
        seq = int(latest[-4:]) + 1 if latest else 1
        return f"{prefix}{seq:04d}"

    def _ensure_can_operate(self, booking: Booking, current_user: User) -> None:
        """学生只能操作自己的预约；管理员不限。"""
        if current_user.role != "admin" and booking.user_id != current_user.id:
            raise self._not_found()

    async def _user_name(self, user_id: int) -> str:
        """取用户显示名，找不到时返回「未知用户」。"""
        name = await self.session.scalar(select(User.name).where(User.id == user_id))
        return name or "未知用户"

    async def _lab_name(self, lab_id: int) -> str:
        """取实验室名称，找不到时返回「未知实验室」。"""
        name = await self.session.scalar(select(Lab.name).where(Lab.id == lab_id))
        return name or "未知实验室"

    async def _build_out_list(self, rows: list[tuple[Booking, str, str]]) -> list[BookingOut]:
        """把「预约 + 学生名 + 实验室名」批量补上设备后转成响应模型。"""
        if not rows:
            return []

        booking_ids = [row[0].id for row in rows]
        device_rows = (
            await self.session.execute(
                select(BookingDevice.booking_id, Device.id, Device.name, Device.model)
                .join(Device, Device.id == BookingDevice.device_id)
                .where(BookingDevice.booking_id.in_(booking_ids))
                .order_by(BookingDevice.id)
            )
        ).all()

        devices_by_booking: dict[int, list[BookingDeviceOut]] = {}
        for booking_id, device_id, name, model in device_rows:
            devices_by_booking.setdefault(booking_id, []).append(
                BookingDeviceOut(id=device_id, name=name, model=model)
            )

        return [
            BookingOut(
                id=booking.id,
                code=booking.code,
                user_id=booking.user_id,
                user_name=user_name,
                lab_id=booking.lab_id,
                lab_name=lab_name,
                booking_date=booking.booking_date,
                start_time=booking.start_time,
                end_time=booking.end_time,
                duration_minutes=booking_rules.duration_minutes(booking.start_time, booking.end_time),
                people_count=booking.people_count,
                booking_type=booking.booking_type,
                purpose=booking.purpose,
                contact_name=booking.contact_name,
                contact_phone=booking.contact_phone,
                status=booking.status,
                reject_reason=booking.reject_reason,
                cancel_requested=booking.cancel_requested,
                cancel_reason=booking.cancel_reason,
                devices=devices_by_booking.get(booking.id, []),
                create_time=booking.create_time,
                reviewed_at=booking.reviewed_at,
            )
            for booking, user_name, lab_name in rows
        ]

    @staticmethod
    def _not_found() -> HTTPException:
        """统一的「预约不存在」异常。"""
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
