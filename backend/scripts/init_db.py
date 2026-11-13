"""按当前 ORM 模型建表（幂等，可重复执行）。

用法（在 backend 目录下）：

    python -m scripts.init_db
"""

import asyncio

from sqlalchemy import text

import app.models  # noqa: F401  导入以注册所有模型
from app.db import Base, close_db, engine


async def main() -> None:
    # create_all 只建「表不存在」的模型，已存在的表不会改动，因此可以重复执行；
    # 注意它不会做迁移：字段增减仍要手写 ALTER 或重建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 打印实际存在的表，确认模型都已注册
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES"))
        print("tables:", [row[0] for row in result])

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
