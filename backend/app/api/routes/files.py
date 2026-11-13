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


@router.post(
    "/upload",
    response_model=Result[FileOut],
    summary="上传文件",
    description="支持头像、实验室封面、预约附件；按 bizType 决定公开目录还是私有目录。",
)
async def upload(
    file: UploadFile = File(..., description="待上传文件"),
    biz_type: str = Form(
        ..., alias="bizType", description="avatar / lab_cover / booking_attachment"
    ),
    biz_id: Optional[int] = Form(None, alias="bizId", description="关联业务主键，可空"),
    current_user: User = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
) -> Result[FileOut]:
    """上传单个文件并写入 file_meta。

    规则：后缀白名单（图片/文档/压缩包）、单文件 ≤20MB、魔数校验；
    avatar 与 lab_cover 写入公开目录并返回可直接访问的 URL，其余按私有文件处理。
    """
    data = await service.upload(
        file=file, biz_type=biz_type, biz_id=biz_id, uploader=current_user
    )
    return Result.ok(data)


@router.get(
    "/{file_id}/download",
    summary="下载文件（私有文件需登录且校验归属）",
    description="公开文件也可走此接口；私有文件仅上传者本人或管理员可下载。",
)
async def download(
    file_id: int,
    current_user: User = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    """下载文件流。

    文件不存在或磁盘丢失返回 404；私有文件越权访问返回 403。
    """
    path, meta = await service.resolve_download(file_id, current_user)
    return FileResponse(path, media_type=meta.mime, filename=meta.original_name)
