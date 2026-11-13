"""文件上传相关的响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel


class FileOut(CamelModel):
    """上传成功后的文件信息。

    ``url`` 有两种形态：公开文件是 ``/media/...``（可直接 <img> 引用），
    私有文件是 ``/api/files/{id}/download``（Request 需带 Bearer token）。
    """

    id: int
    biz_type: str
    url: str = Field(description="公开文件是 /media/...，私有文件是鉴权下载地址")
    name: str
    size: int
    mime: str
    is_public: bool
    create_time: Optional[datetime] = None
