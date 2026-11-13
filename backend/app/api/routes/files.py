"""文件接口：只做参数接收、鉴权与响应封装。

业务实现在 ``app.services.file_service.FileService``。
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_current_user, get_file_service
from app.core.result import Result
from app.models import User
from app.schemas import FileOut
from app.services import FileService

router = APIRouter(prefix="/api/files", tags=["files"])


# POST /api/files/upload 上传文件
# 支持头像、实验室封面、预约附件；按 bizType 决定公开目录还是私有目录。
# avatar 与 lab_cover 写入公开目录，返回可直接访问的 URL；
# 其余按私有文件处理，返回需要鉴权的下载地址。
#
# Args:
#     file: 待上传文件，不落临时文件，边读边写。
#     biz_type: 业务类型，决定公开/私有目录与子路径。
#     biz_id: 关联业务主键，可为空。
#     current_user: 当前登录用户（鉴权依赖），记为上传者。
#     service: 文件业务服务（依赖注入）。
#
# Returns:
#     Result[FileOut]: code=200，data 含文件 id、url、name、size、mime 等。
#
# Raises:
#     HTTPException 400: 后缀不在白名单、超过 20MB 或内容与后缀不符。
#     HTTPException 401: 未登录或令牌失效。
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
    """上传单个文件并写入 file_meta。"""
    data = await service.upload(
        file=file, biz_type=biz_type, biz_id=biz_id, uploader=current_user
    )
    return Result.ok(data)


# GET /api/files/{file_id}/download 下载文件
# 公开文件也可走此接口；私有文件仅上传者本人或管理员可下载。
#
# Args:
#     file_id: 文件元数据主键。
#     current_user: 当前登录用户（鉴权依赖），用于私有文件归属校验。
#     service: 文件业务服务（依赖注入）。
#
# Returns:
#     FileResponse: 带原始文件名与 MIME 类型的文件流。
#
# Raises:
#     HTTPException 403: 当前用户无权访问该私有文件。
#     HTTPException 404: 文件记录不存在或磁盘上的文件已丢失。
@router.get(
    "/{file_id}/download",
    summary="下载文件（私有文件需登录且校验归属）",
    description="公开文件也可走此接口；私有文件仅上传者本人或管理员可下载。",
)
async def download(
    file_id: int,
    current_user: User = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
) -> FileResponse:
    """下载文件流。"""
    path, meta = await service.resolve_download(file_id, current_user)
    return FileResponse(path, media_type=meta.mime, filename=meta.original_name)
