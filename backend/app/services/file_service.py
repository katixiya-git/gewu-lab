"""文件上传与下载业务逻辑：落盘、元数据入库、私有文件鉴权。

本模块只处理业务规则与数据读写，不感知 HTTP 路由；接口层见
``app.api.routes.files``。
"""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models import FileMeta, User
from app.schemas import FileOut


class FileService:
    """文件业务服务。"""

    def __init__(self, session: AsyncSession) -> None:
        """Args:
            session: 由接口层依赖注入的异步数据库会话。
        """
        self.session = session

    async def upload(
        self,
        *,
        file: UploadFile,
        biz_type: str,
        biz_id: int | None,
        uploader: User,
    ) -> FileOut:
        """保存上传文件并写入元数据。

        文件校验（后缀白名单、大小上限、魔数）由 ``storage.save_upload``
        负责；``avatar`` 与 ``lab_cover`` 落到公开目录，其余按私有文件处理。

        Args:
            file: 上传的文件对象，处理完会关闭。
            biz_type: 业务类型，``avatar`` / ``lab_cover`` / ``booking_attachment``。
            biz_id: 关联业务主键，可为空。
            uploader: 上传者（由接口层鉴权后传入）。

        Returns:
            FileOut: 文件元数据与可访问 URL。

        Raises:
            HTTPException 400: 后缀不在白名单、文件超过大小限制或内容与后缀不符。
        """
        try:
            saved = await storage.save_upload(file, biz_type)
        except storage.UploadError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
        finally:
            await file.close()

        meta = FileMeta(
            biz_type=biz_type,
            biz_id=biz_id,
            original_name=saved.original_name,
            stored_path=saved.stored_path,
            suffix=saved.suffix,
            mime=saved.mime,
            size=saved.size,
            sha256=saved.sha256,
            is_public=saved.is_public,
            uploader_id=uploader.id,
        )
        self.session.add(meta)
        await self.session.commit()
        await self.session.refresh(meta)

        return self._to_out(meta)

    async def resolve_download(
        self, file_id: int, user: User
    ) -> tuple[Path, FileMeta]:
        """校验下载权限并返回磁盘路径。

        公开文件任何登录用户可下载；私有文件仅上传者本人或管理员可下载。

        Args:
            file_id: 文件元数据主键。
            user: 当前登录用户（由接口层鉴权后传入）。

        Returns:
            tuple[Path, FileMeta]: 文件磁盘路径与元数据。

        Raises:
            HTTPException 404: 文件记录不存在，或磁盘上的文件已丢失。
            HTTPException 403: 无权访问该私有文件。
        """
        meta = await self.session.get(FileMeta, file_id)
        if meta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
            )

        if (
            not meta.is_public
            and meta.uploader_id != user.id
            and user.role != "admin"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件"
            )

        path = storage.absolute_path(meta.stored_path, meta.is_public)
        if not path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失"
            )
        return path, meta

    @staticmethod
    def _to_out(meta: FileMeta) -> FileOut:
        """把文件元数据转换成响应模型。

        Args:
            meta: 文件元数据 ORM 对象。

        Returns:
            FileOut: 含公开 URL 或鉴权下载地址的响应对象。
        """
        url = (
            storage.public_url(meta.stored_path)
            if meta.is_public
            else f"/api/files/{meta.id}/download"
        )
        return FileOut(
            id=meta.id,
            biz_type=meta.biz_type,
            url=url,
            name=meta.original_name,
            size=meta.size,
            mime=meta.mime,
            is_public=meta.is_public,
            create_time=meta.create_time,
        )
