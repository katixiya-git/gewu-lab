"""种子账号：管理员与学生各一个，重复执行会跳过已存在的账号。

用法（在 backend 目录下，先装好 bcrypt）：

    python -m scripts.seed_users

默认密码均为 123456（仅演示环境使用）。
"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db import SessionLocal, close_db
from app.models import User

SEED_USERS = [
    {
        "username": "admin",
        "password": "123456",
        "name": "王老师",
        "role": "admin",
        "phone": "13800000001",
        "email": "admin@gewu.local",
        "avatar": None,
    },
    {
        "username": "student",
        "password": "123456",
        "name": "张同学",
        "role": "student",
        "phone": "13800000002",
        "email": "student@gewu.local",
        "avatar": None,
    },
]


async def main() -> None:
    async with SessionLocal() as session:
        for item in SEED_USERS:
            # 幂等：按用户名判断，已存在就跳过，避免重复插入撞唯一索引
            exists = await session.scalar(select(User).where(User.username == item["username"]))
            if exists is not None:
                print(f"skip  {item['username']}（已存在，id={exists.id}）")
                continue

            user = User(
                username=item["username"],
                password_hash=hash_password(item["password"]),
                name=item["name"],
                role=item["role"],
                phone=item["phone"],
                email=item["email"],
                avatar=item["avatar"],
            )
            session.add(user)
            print(f"add   {item['username']} / {item['password']}（{item['role']}）")

        # 循环内只 add，最后统一提交；中途失败则一条都不落库
        await session.commit()

        rows = (await session.scalars(select(User).order_by(User.id))).all()
        print("\n当前用户：")
        for row in rows:
            print(f"  {row.id:>2}  {row.username:<8} {row.name:<6} {row.role:<8} {row.status}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
