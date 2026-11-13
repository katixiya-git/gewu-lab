"""文件上传与私有文件下载接口：只做参数接收、鉴权与响应封装。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_current_user, get_file_service
from app.core.result import Result
from app.models import User
from app.schemas import FileOut
from app.services import FileService

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=Result[FileOut], summary="上传文件")
async def upload(
    file: UploadFile = File(..., description="待上传文件"),
    biz_type: str = Form(
        ..., alias="bizType", description="avatar / lab_cover / booking_attachment"
    ),
    biz_id: Optional[int] = Form(None, alias="bizId", description="关联业务主键，可空"),
    current_user: User = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
) -> Result[FileOut]:
    data = await service.upload(
        file=file, biz_type=biz_type, biz_id=biz_id, uploader=current_user
    )
    return Result.ok(data)


@router.get("/{file_id}/download", summary="下载文件（私有文件需登录且校验归属）")
async def download(
    file_id: int,
    current_user: User = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    path, meta = await service.resolve_download(file_id, current_user)
    return FileResponse(path, media_type=meta.mime, filename=meta.original_name)
