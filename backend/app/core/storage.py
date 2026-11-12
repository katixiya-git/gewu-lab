"""本地磁盘存储：后缀白名单、魔数校验、随机文件名落盘。

目录结构（相对 upload_dir）：

    public/avatar/2026/11/<uuid>.jpg
    public/lab-cover/2026/11/<uuid>.png
    private/attachments/2026/11/<uuid>.pdf
"""

import hashlib
import mimetypes
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.config import get_settings

# 允许上传的后缀（小写，含点）
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
    ".docx": [b"PK\x03\x04"],
    ".xlsx": [b"PK\x03\x04"],
    ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}


class UploadError(ValueError):
    """上传校验失败，路由层转成 400。"""


@dataclass
class SavedFile:
    stored_path: str
    original_name: str
    suffix: str
    mime: str
    size: int
    sha256: str
    is_public: bool


def upload_root() -> Path:
    return Path(get_settings().upload_dir).resolve()


def public_root() -> Path:
    return upload_root() / "public"


def ensure_upload_dirs() -> None:
    """启动时建好公开/私有根目录，StaticFiles 挂载要求目录存在。"""
    for path in (public_root(), upload_root() / "private"):
        path.mkdir(parents=True, exist_ok=True)


def get_suffix(filename: str | None) -> str:
    if not filename:
        raise UploadError("文件名为空")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUFFIX_WHITELIST:
        allowed = " ".join(sorted(SUFFIX_WHITELIST))
        raise UploadError(f"不支持的文件类型，仅允许：{allowed}")
    return suffix


def check_magic(head: bytes, suffix: str) -> None:
    if suffix == ".webp":
        # RIFF....WEBP
        if not (len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
            raise UploadError("文件内容与扩展名不符")
        return

    signatures = _MAGIC.get(suffix)
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise UploadError("文件内容与扩展名不符")


def build_stored_name(suffix: str) -> str:
    now = datetime.now()
    return f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}{suffix}"


async def save_upload(file, biz_type: str) -> SavedFile:
    """流式落盘并做大小/魔数校验，返回元数据。"""
    if biz_type not in BIZ_DIRS:
        raise UploadError(f"未知的业务类型：{biz_type}")

    suffix = get_suffix(file.filename)
    is_public = biz_type in PUBLIC_BIZ_TYPES
    max_bytes = get_settings().upload_max_mb * 1024 * 1024

    stored_rel = build_stored_name(suffix)
    base = upload_root() / ("public" if is_public else "private") / BIZ_DIRS[biz_type]
    target = base / stored_rel
    target.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    size = 0
    head = b""

    with target.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            if not head:
                head = chunk[:16]
                check_magic(head, suffix)
            size += len(chunk)
            if size > max_bytes:
                out.close()
                target.unlink(missing_ok=True)
                raise UploadError(f"文件超过 {get_settings().upload_max_mb}MB 限制")
            digest.update(chunk)
            out.write(chunk)

    if size == 0:
        target.unlink(missing_ok=True)
        raise UploadError("文件内容为空")

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
    return f"/media/{stored_path}"


def absolute_path(stored_path: str, is_public: bool) -> Path:
    base = public_root() if is_public else upload_root() / "private"
    return base / stored_path
