"""本地磁盘存储：后缀白名单、魔数校验、随机文件名落盘。

目录结构（相对 ``upload_dir``）：

    public/avatar/2026/11/<uuid>.jpg      ← 头像，公开可读（/media 静态托管）
    public/lab-cover/2026/11/<uuid>.png   ← 实验室封面，公开可读
    private/attachments/2026/11/<uuid>.pdf ← 预约附件，私有，走鉴权下载

约定：文件名一律用 uuid，不用用户上传的原始名，避免路径穿越与重名覆盖；
原始文件名只记在数据库里供下载时回显。
"""

import hashlib
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.config import get_settings

# 允许上传的后缀（小写，含点）；新增类型需同时补 _MAGIC
SUFFIX_WHITELIST = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}

# 公开可读的业务类型；其余一律私有，走鉴权下载
PUBLIC_BIZ_TYPES = {"avatar", "lab_cover"}

# 业务类型 → 子目录名（下划线转中划线，URL 更规范）
BIZ_DIRS = {
    "avatar": "avatar",
    "lab_cover": "lab-cover",
    "booking_attachment": "attachments",
}

# 文件头魔数：扩展名可以改，文件头改不了，两者必须一致
_MAGIC = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".pdf": [b"%PDF"],
    ".zip": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    ".docx": [b"PK\x03\x04"],  # docx 本质是 zip
    ".xlsx": [b"PK\x03\x04"],  # xlsx 本质是 zip
    ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # 老版 OLE 复合文档
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}


class UploadError(ValueError):
    """上传校验失败，路由层统一转成 400。"""


@dataclass
class SavedFile:
    """落盘成功后返回给业务层的元数据。"""

    stored_path: str  # 相对 upload_dir 的路径，如 avatar/2026/11/xx.png
    original_name: str
    suffix: str
    mime: str
    size: int
    sha256: str
    is_public: bool


def upload_root() -> Path:
    """上传根目录（绝对路径），默认 backend/uploads。"""
    return Path(get_settings().upload_dir).resolve()


def public_root() -> Path:
    """公开文件根目录，挂载为 /media。"""
    return upload_root() / "public"


def ensure_upload_dirs() -> None:
    """启动时建好公开/私有根目录，StaticFiles 挂载要求目录存在。"""
    for path in (public_root(), upload_root() / "private"):
        path.mkdir(parents=True, exist_ok=True)


def get_suffix(filename: str | None) -> str:
    """取小写后缀并校验白名单。

    Args:
        filename: 用户上传时的原始文件名。

    Returns:
        str: 形如 ``.png`` 的后缀。

    Raises:
        UploadError: 文件名为空或后缀不在白名单。
    """
    if not filename:
        raise UploadError("文件名为空")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUFFIX_WHITELIST:
        allowed = " ".join(sorted(SUFFIX_WHITELIST))
        raise UploadError(f"不支持的文件类型，仅允许：{allowed}")
    return suffix


def check_magic(head: bytes, suffix: str) -> None:
    """校验文件头魔数与后缀是否匹配。

    webp 的结构是 ``RIFF....WEBP``，不是简单前缀，单独判断。

    Args:
        head: 文件前 16 字节。
        suffix: 已通过白名单的小写后缀。

    Raises:
        UploadError: 内容与扩展名不符（例如把 exe 改成 .png）。
    """
    if suffix == ".webp":
        # RIFF....WEBP
        if not (len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
            raise UploadError("文件内容与扩展名不符")
        return

    signatures = _MAGIC.get(suffix)
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise UploadError("文件内容与扩展名不符")


def build_stored_name(suffix: str) -> str:
    """生成存储相对路径：``年/月/uuid.ext``。

    用 uuid 而不是原名：避免重名覆盖、路径穿越（``../``），也便于水平扩展。
    """
    now = datetime.now()
    return f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}{suffix}"


async def save_upload(file, biz_type: str) -> SavedFile:
    """流式落盘并做大小/魔数校验，返回元数据。

    逐块（1MB）读取并写入，避免大文件一次性进内存；读到第一块时立即
    校验魔数，不合法马上中止并删除半成品文件。

    Args:
        file: FastAPI 的 UploadFile，需提供 ``filename`` 与 ``read``。
        biz_type: ``avatar`` / ``lab_cover`` / ``booking_attachment``。

    Returns:
        SavedFile: 存储路径、大小、sha256 等元数据。

    Raises:
        UploadError: 业务类型未知、后缀非法、内容与后缀不符、超限或空文件。
    """
    if biz_type not in BIZ_DIRS:
        raise UploadError(f"未知的业务类型：{biz_type}")

    suffix = get_suffix(file.filename)
    is_public = biz_type in PUBLIC_BIZ_TYPES
    max_bytes = get_settings().upload_max_mb * 1024 * 1024

    stored_rel = build_stored_name(suffix)
    base = upload_root() / ("public" if is_public else "private") / BIZ_DIRS[biz_type]
    target = base / stored_rel
    target.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()  # 内容哈希，可用于去重/审计
    size = 0
    head = b""

    with target.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            if not head:
                # 第一块才拿得到文件头；这里失败会直接跳出去删除文件
                head = chunk[:16]
                check_magic(head, suffix)
            size += len(chunk)
            if size > max_bytes:
                out.close()
                target.unlink(missing_ok=True)  # 超限不留半成品
                raise UploadError(f"文件超过 {get_settings().upload_max_mb}MB 限制")
            digest.update(chunk)
            out.write(chunk)

    if size == 0:
        target.unlink(missing_ok=True)
        raise UploadError("文件内容为空")

    # 用后缀猜 MIME；猜不到给通用二进制类型
    mime = mimetypes.guess_type(f"x{suffix}")[0] or "application/octet-stream"
    return SavedFile(
        stored_path=f"{BIZ_DIRS[biz_type]}/{stored_rel}",
        original_name=file.filename or f"file{suffix}",
        suffix=suffix,
        mime=mime,
        size=size,
        sha256=digest.hexdigest(),
        is_public=is_public,
    )


def public_url(stored_path: str) -> str:
    """公开文件的访问地址（由 main.py 的 /media 静态挂载提供服务）。"""
    return f"/media/{stored_path}"


def absolute_path(stored_path: str, is_public: bool) -> Path:
    """把数据库里的相对路径还原成磁盘绝对路径，用于下载。"""
    base = public_root() if is_public else upload_root() / "private"
    return base / stored_path
