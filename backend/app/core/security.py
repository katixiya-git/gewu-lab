"""密码哈希（bcrypt）与 JWT 签发/解析。

密码只存 bcrypt 哈希，不可逆；JWT 只放用户 id 和角色，不放敏感信息。
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希。

    每次调用 ``gensalt()`` 都会生成新盐，因此同一密码两次哈希结果不同，
    校验必须用 ``verify_password`` 而不是比较字符串。

    Args:
        password: 明文密码。

    Returns:
        str: 形如 ``$2b$12$...`` 的哈希字符串。
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。

    哈希损坏（非 bcrypt 格式）时 bcrypt 会抛 ValueError，这里吞掉并返回
    False，避免脏数据导致 500。

    Args:
        password: 用户输入的明文密码。
        password_hash: 数据库里的 bcrypt 哈希。

    Returns:
        bool: 匹配返回 True，否则 False。
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, role: str) -> str:
    """签发 JWT。

    payload 约定：``sub`` 用户 id、``role`` 角色、``iat`` 签发时间、
    ``exp`` 过期时间（由 ``jwt_expire_minutes`` 控制）。

    Args:
        user_id: 用户主键。
        role: ``student`` 或 ``admin``。

    Returns:
        str: 编码后的 JWT 字符串。
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解析并校验 JWT。

    过期、签名不符、格式错误都会抛 ``jwt.InvalidTokenError`` 的子类，
    由调用方（``get_current_user``）转成 401。

    Args:
        token: 请求头里的原始令牌。

    Returns:
        dict: 解码后的 payload。
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
