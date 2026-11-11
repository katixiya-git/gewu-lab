"""密码哈希与校验：bcrypt。"""

import bcrypt


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希（每次盐不同，结果不可逆）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配；哈希损坏时返回 False 而不是抛异常。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
