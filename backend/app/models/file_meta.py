from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FileMeta(Base):
    """上传文件元数据：磁盘上只存字节，关系都在这里。"""

    __tablename__ = "file_meta"
    __table_args__ = {"comment": "上传文件元数据"}

    biz_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="业务类型：avatar/lab_cover/booking_attachment"
    )
    biz_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, index=True, comment="关联业务主键（可空）"
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    stored_path: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="相对 upload_dir 的存储路径"
    )
    suffix: Mapped[str] = mapped_column(String(10), nullable=False, comment="扩展名（含点）")
    mime: Mapped[str] = mapped_column(String(100), nullable=False, comment="MIME 类型")
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件大小（字节）")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="内容哈希")
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1", comment="是否公开可读"
    )
    uploader_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="上传人 user.id"
    )

    def __repr__(self) -> str:
        return f"<FileMeta id={self.id} {self.biz_type} {self.original_name!r}>"
