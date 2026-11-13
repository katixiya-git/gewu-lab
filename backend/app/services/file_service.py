"""文件上传与下载的业务逻辑：落盘、元数据入库、私有文件鉴权。"""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models import FileMeta, User
from app.schemas import FileOut


class FileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upload(
        self,
        *,
        file: UploadFile,
        biz_type: str,
        biz_id: int | None,
        uploader: User,
    ) -> FileOut:
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
