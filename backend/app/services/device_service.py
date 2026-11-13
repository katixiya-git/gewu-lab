"""设备业务服务：分页、增删改、状态切换与跨表规则校验。

学生端可见性在这里收口：设备所属实验室必须启用，且设备本身不能是
``disabled``（``maintenance`` 仍展示，前端用灰色标签说明暂时不可用）。
"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Lab, User
from app.schemas.device import (
    DeviceCreateRequest,
    DeviceOut,
    DevicePageOut,
    DeviceStatusRequest,
    DeviceUpdateRequest,
)


class DeviceService:
    """设备管理的业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        """Args:
            session: 由接口层依赖注入的异步数据库会话。
        """
        self.session = session

    async def page(
        self,
        *,
        current_user: User,
        page: int,
        size: int,
        keyword: str | None,
        lab_id: int | None,
        status_filter: str | None,
    ) -> DevicePageOut:
        """按条件分页查询设备。

        学生只能看到启用实验室下、非 ``disabled`` 的设备。

        Args:
            current_user: 当前登录用户。
            page: 页码，从 1 开始。
            size: 每页条数，1–50。
            keyword: 可选关键词，匹配设备名/型号/备注。
            lab_id: 可选的实验室过滤。
            status_filter: 可选状态过滤，仅管理员生效。

        Returns:
            DevicePageOut: 总条数与当前页设备列表。
        """
        conditions = []

        if current_user.role != "admin":
            conditions.append(Lab.status == "enabled")
            conditions.append(Device.status != "disabled")
        elif status_filter in ("normal", "maintenance", "disabled"):
            conditions.append(Device.status == status_filter)

        if lab_id is not None:
            conditions.append(Device.lab_id == lab_id)

        if keyword and keyword.strip():
            like = f"%{keyword.strip()}%"
            conditions.append(
                or_(Device.name.like(like), Device.model.like(like), Device.note.like(like))
            )

        base = select(Device, Lab.name).join(Lab, Device.lab_id == Lab.id).where(*conditions)
        total = await self.session.scalar(
            select(func.count())
            .select_from(Device)
            .join(Lab, Device.lab_id == Lab.id)
            .where(*conditions)
        )

        rows = (
            await self.session.execute(
                base.order_by(Device.sort_order, Device.id).offset((page - 1) * size).limit(size)
            )
        ).all()

        items = [self._to_out(device, lab_name) for device, lab_name in rows]
        return DevicePageOut(total=total or 0, items=items)

    async def get(self, device_id: int, *, current_user: User) -> DeviceOut:
        """按 id 查询设备详情。

        学生访问停用实验室或停用设备时返回 404，避免暴露内部资源。

        Args:
            device_id: 设备 id。
            current_user: 当前登录用户。

        Returns:
            DeviceOut: 设备详情。

        Raises:
            HTTPException 404: 设备不存在，或学生无权查看。
        """
        device = await self._get_or_404(device_id)
        if current_user.role != "admin":
            lab = await self.session.get(Lab, device.lab_id)
            if lab is None or lab.status != "enabled" or device.status == "disabled":
                raise self._not_found()
        else:
            lab = await self.session.get(Lab, device.lab_id)
        return self._to_out(device, lab.name if lab else "")

    async def create(self, payload: DeviceCreateRequest) -> DeviceOut:
        """新增设备。

        Args:
            payload: 已通过 schema 校验的新增入参。

        Returns:
            DeviceOut: 新建后的设备。

        Raises:
            HTTPException 404: 实验室不存在。
            HTTPException 409: 同一实验室下设备名重复。
        """
        lab = await self._get_lab_or_404(payload.lab_id)
        await self._ensure_name_available(payload.lab_id, payload.name)

        device = Device(**payload.model_dump())
        self.session.add(device)
        await self._commit_or_conflict()
        await self.session.refresh(device)
        return self._to_out(device, lab.name)

    async def update(self, device_id: int, payload: DeviceUpdateRequest) -> DeviceOut:
        """编辑设备，只修改提交过的字段。

        换实验室或改名时，会在目标实验室里重新查重。

        Args:
            device_id: 设备 id。
            payload: 编辑入参，未传字段保持不变。

        Returns:
            DeviceOut: 更新后的设备。

        Raises:
            HTTPException 404: 设备或目标实验室不存在。
            HTTPException 409: 目标实验室下设备名重复。
        """
        device = await self._get_or_404(device_id)
        data = payload.model_dump(exclude_unset=True)

        target_lab_id = data.get("lab_id", device.lab_id)
        target_name = data.get("name", device.name)
        lab = await self._get_lab_or_404(target_lab_id)
        if target_lab_id != device.lab_id or target_name != device.name:
            await self._ensure_name_available(target_lab_id, target_name, exclude_id=device.id)

        for field, value in data.items():
            setattr(device, field, value)

        await self._commit_or_conflict()
        await self.session.refresh(device)
        return self._to_out(device, lab.name)

    async def change_status(self, device_id: int, payload: DeviceStatusRequest) -> DeviceOut:
        """启用 / 维护 / 停用设备。

        Args:
            device_id: 设备 id。
            payload: 目标状态。

        Returns:
            DeviceOut: 更新后的设备。

        Raises:
            HTTPException 404: 设备不存在。
        """
        device = await self._get_or_404(device_id)
        device.status = payload.status
        await self.session.commit()
        await self.session.refresh(device)
        lab = await self.session.get(Lab, device.lab_id)
        return self._to_out(device, lab.name if lab else "")

    async def delete(self, device_id: int) -> None:
        """删除设备。

        当前没有预约明细引用设备，先做物理删除；预约模块落地后要改成
        有引用时拒绝删除或软删除。

        Args:
            device_id: 设备 id。

        Raises:
            HTTPException 404: 设备不存在。
        """
        device = await self._get_or_404(device_id)
        await self.session.delete(device)
        await self.session.commit()

    async def count_by_lab(self, lab_id: int) -> int:
        """统计某实验室下的设备数量，供实验室删除守卫使用。"""
        return await self.session.scalar(
            select(func.count()).select_from(Device).where(Device.lab_id == lab_id)
        ) or 0

    async def _get_or_404(self, device_id: int) -> Device:
        """按 id 取设备，不存在抛 404。"""
        device = await self.session.get(Device, device_id)
        if device is None:
            raise self._not_found()
        return device

    async def _get_lab_or_404(self, lab_id: int) -> Lab:
        """按 id 取实验室，不存在抛 404。"""
        lab = await self.session.get(Lab, lab_id)
        if lab is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实验室不存在")
        return lab

    async def _ensure_name_available(
        self, lab_id: int, name: str, *, exclude_id: int | None = None
    ) -> None:
        """同一实验室内设备名重复直接 409，先查一次给出友好提示。"""
        conditions = [Device.lab_id == lab_id, Device.name == name]
        if exclude_id is not None:
            conditions.append(Device.id != exclude_id)
        exists = await self.session.scalar(select(Device.id).where(*conditions))
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="该实验室下已存在同名设备"
            )

    async def _commit_or_conflict(self) -> None:
        """提交事务；并发下撞唯一索引也转成 409，而不是 500。"""
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="该实验室下已存在同名设备"
            ) from exc

    @staticmethod
    def _not_found() -> HTTPException:
        """统一的「设备不存在」异常。"""
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

    @staticmethod
    def _to_out(device: Device, lab_name: str) -> DeviceOut:
        """把 ORM 对象与联表得到的实验室名组装成响应模型。"""
        return DeviceOut(
            id=device.id,
            lab_id=device.lab_id,
            lab_name=lab_name,
            name=device.name,
            model=device.model,
            total_count=device.total_count,
            status=device.status,
            note=device.note,
            sort_order=device.sort_order,
            create_time=device.create_time,
        )
