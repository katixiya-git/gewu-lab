"""文件上传与私有文件下载。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core import storage
from app.core.result import Result
from app.db import get_session
from app.models import FileMeta, User
from app.schemas import FileOut

router = APIRouter(prefix="/api/files", tags=["files"])


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


@router.post("/upload", response_model=Result[FileOut], summary="上传文件")
async def upload(
    file: UploadFile = File(..., description="待上传文件"),
    biz_type: str = Form(..., alias="bizType", description="avatar / lab_cover / booking_attachment"),
    biz_id: Optional[int] = Form(None, alias="bizId", description="关联业务主键，可空"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Result[FileOut]:
    try:
        saved = await storage.save_upload(file, biz_type)
    except storage.UploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
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
        uploader_id=current_user.id,
    )
    session.add(meta)
    await session.commit()
    await session.refresh(meta)

    return Result.ok(_to_out(meta))


@router.get("/{file_id}/download", summary="下载文件（私有文件需登录且校验归属）")
async def download(
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    meta = await session.get(FileMeta, file_id)
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    if not meta.is_public and meta.uploader_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")

    path = storage.absolute_path(meta.stored_path, meta.is_public)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")

    return FileResponse(path, media_type=meta.mime, filename=meta.original_name)
