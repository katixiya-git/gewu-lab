"""设备表 ORM 模型。

设备从属于某一间实验室：同一实验室内设备名唯一，跨实验室允许重名。
``total_count`` 是登记数量，不等同于「当前可借数量」——预约模块落地后
要按日期与时段另行计算占用，不能直接改这个字段。
"""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Device(Base):
    """实验室设备：名称、型号、数量、状态与备注。"""

    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("lab_id", "name", name="uq_devices_lab_name"),
        {"comment": "实验室设备表"},
    )

    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="所属实验室 id",
    )

    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="设备名称，同一实验室内唯一",
    )

    model: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="型号，如 RTX 4090",
    )

    total_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="登记数量（不是实时可借数量）",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="normal",
        server_default="normal",
        index=True,
        comment="状态：normal 正常 / maintenance 维护中 / disabled 停用",
    )

    note: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="备注，如「需两人在场」",
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="排序，越小越靠前",
    )

    def __repr__(self) -> str:
        """便于日志里快速识别设备。"""
        return f"<Device id={self.id} lab_id={self.lab_id} name={self.name!r}>"
