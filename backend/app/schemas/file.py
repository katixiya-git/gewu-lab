"""文件上传相关的响应模型。"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import CamelModel


class FileOut(CamelModel):
    id: int
    biz_type: str
    url: str = Field(description="公开文件是 /media/...，私有文件是鉴权下载地址")
    name: str
    size: int
    mime: str
    is_public: bool
    create_time: Optional[datetime] = None
