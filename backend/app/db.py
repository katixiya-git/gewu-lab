from typing import Optional

import aiomysql
from aiomysql import Pool

from app.config import get_settings

_pool: Optional[Pool] = None


async def init_db_pool() -> Pool:
    """创建全局连接池（应用启动时调用一次）。"""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await aiomysql.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            db=settings.db_name,
            charset="utf8mb4",
            autocommit=True,
            minsize=1,
            maxsize=10,
        )
    return _pool


async def close_db_pool() -> None:
    """关闭连接池（应用退出时调用）。"""
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


def get_pool() -> Pool:
    """获取连接池，未初始化时直接报错，避免静默返回 None。"""
    if _pool is None:
        raise RuntimeError("数据库连接池未初始化，请先调用 init_db_pool()")
    return _pool


async def ping() -> bool:
    """执行 SELECT 1，用于启动自检或健康检查。"""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            row = await cur.fetchone()
    return bool(row and row[0] == 1)
