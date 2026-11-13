"""实验室业务服务：分页查询、增删改、启停与业务规则校验。

本模块只处理业务规则与数据读写，不感知 HTTP 路由；接口层见
``app.api.routes.labs``。
"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, Lab, User
from app.schemas.lab import (
    LabCreateRequest,
    LabOut,
    LabPageOut,
    LabStatusRequest,
    LabUpdateRequest,
)


class LabService:
    """实验室管理的业务服务。"""

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
        category: str | None,
        status_filter: str | None,
    ) -> LabPageOut:
        """按条件分页查询实验室。

        学生端强制只看 ``enabled``，传入的 ``status`` 会被忽略；管理员可以
        按状态筛选。关键词同时模糊匹配名称与位置。

        Args:
            current_user: 当前登录用户。
            page: 页码，从 1 开始。
            size: 每页条数，1–50。
            keyword: 可选关键词，最长 50 字符。
            category: 可选的类型码过滤。
            status_filter: 可选的状态过滤，仅管理员生效。

        Returns:
            LabPageOut: 总条数与当前页实验室列表。
        """
        conditions = []

        if current_user.role != "admin":
            conditions.append(Lab.status == "enabled")
        elif status_filter in ("enabled", "disabled"):
            conditions.append(Lab.status == status_filter)

        if category in ("ai", "robot", "cloud", "se"):
            conditions.append(Lab.category == category)

        if keyword and keyword.strip():
            like = f"%{keyword.strip()}%"
            conditions.append(or_(Lab.name.like(like), Lab.location.like(like)))

        total = await self.session.scalar(select(func.count()).select_from(Lab).where(*conditions))

        rows = (
            await self.session.scalars(
                select(Lab)
                .where(*conditions)
                .order_by(Lab.sort_order, Lab.id)
                .offset((page - 1) * size)
                .limit(size)
            )
        ).all()

        return LabPageOut(total=total or 0, items=[LabOut.model_validate(row) for row in rows])

    async def get(self, lab_id: int, *, current_user: User) -> LabOut:
        """按 id 查询实验室详情。

        学生访问停用实验室时返回 404（视作不存在），避免暴露内部资源。

        Args:
            lab_id: 实验室 id。
            current_user: 当前登录用户。

        Returns:
            LabOut: 实验室详情。

        Raises:
            HTTPException 404: 实验室不存在，或学生访问停用的实验室。
        """
        lab = await self._get_or_404(lab_id)
        if current_user.role != "admin" and lab.status != "enabled":
            raise self._not_found()
        return LabOut.model_validate(lab)

    async def create(self, payload: LabCreateRequest) -> LabOut:
        """新增实验室。

        Args:
            payload: 已通过 schema 校验的新增入参。

        Returns:
            LabOut: 新建后的实验室。

        Raises:
            HTTPException 409: 名称已存在。
        """
        await self._ensure_name_available(payload.name)

        lab = Lab(**payload.model_dump())
        self.session.add(lab)
        await self._commit_or_conflict()
        await self.session.refresh(lab)
        return LabOut.model_validate(lab)

    async def update(self, lab_id: int, payload: LabUpdateRequest) -> LabOut:
        """编辑实验室，只修改提交过的字段。

        只改开始或结束时间中的一个时，用旧值补齐后再校验先后。

        Args:
            lab_id: 实验室 id。
            payload: 编辑入参，未传字段保持不变。

        Returns:
            LabOut: 更新后的实验室。

        Raises:
            HTTPException 404: 实验室不存在。
            HTTPException 409: 名称重复。
            HTTPException 400: 结束时间不晚于开始时间。
        """
        lab = await self._get_or_404(lab_id)
        data = payload.model_dump(exclude_unset=True)

        if "name" in data and data["name"] != lab.name:
            await self._ensure_name_available(data["name"])

        open_time = data.get("open_time", lab.open_time)
        close_time = data.get("close_time", lab.close_time)
        if close_time <= open_time:
            raise HTTPException(status_code=400, detail="开放结束时间必须晚于开始时间")

        for field, value in data.items():
            setattr(lab, field, value)

        await self._commit_or_conflict()
        await self.session.refresh(lab)
        return LabOut.model_validate(lab)

    async def change_status(self, lab_id: int, payload: LabStatusRequest) -> LabOut:
        """启用或停用实验室。

        Args:
            lab_id: 实验室 id。
            payload: 目标状态。

        Returns:
            LabOut: 更新后的实验室。

        Raises:
            HTTPException 404: 实验室不存在。
        """
        lab = await self._get_or_404(lab_id)
        lab.status = payload.status
        await self.session.commit()
        await self.session.refresh(lab)
        return LabOut.model_validate(lab)

    async def delete(self, lab_id: int) -> None:
        """删除实验室。

        实验室下还有设备时拒绝删除，避免产生孤儿设备；预约模块落地后
        还需要补「存在未结束预约则拒绝删除」的规则。

        Args:
            lab_id: 实验室 id。

        Raises:
            HTTPException 404: 实验室不存在。
            HTTPException 409: 实验室下仍有设备。
        """
        lab = await self._get_or_404(lab_id)
        device_count = await self.session.scalar(
            select(func.count()).select_from(Device).where(Device.lab_id == lab_id)
        )
        if device_count:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="请先移除该实验室下的设备",
            )
        await self.session.delete(lab)
        await self.session.commit()

    async def _get_or_404(self, lab_id: int) -> Lab:
        """按 id 取实验室，不存在抛 404。"""
        lab = await self.session.get(Lab, lab_id)
        if lab is None:
            raise self._not_found()
        return lab

    async def _ensure_name_available(self, name: str) -> None:
        """名称重复直接 409，先查一次给出友好提示。"""
        exists = await self.session.scalar(select(Lab.id).where(Lab.name == name))
        if exists is not None:
            raise HTTPException(status_code=409, detail="实验室名称已存在")

    async def _commit_or_conflict(self) -> None:
        """提交事务；并发下撞唯一索引也转成 409，而不是 500。"""
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="实验室名称已存在") from exc

    @staticmethod
    def _not_found() -> HTTPException:
        """统一的「实验室不存在」异常。"""
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实验室不存在")
