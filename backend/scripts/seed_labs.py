"""实验室种子数据：4 间实验室，按名称幂等写入。

用法（在 backend 目录下，先执行过 ``python -m scripts.init_db``）：

    python -m scripts.seed_labs
"""

import asyncio
from datetime import time

from sqlalchemy import select

from app.db import SessionLocal, close_db
from app.models import Lab

# 与前端 mock 对齐的 4 间实验室；open_days 用「1-7」表示周一至周日
SEED_LABS = [
    {
        "name": "人工智能实验室",
        "category": "ai",
        "location": "实验楼 A301",
        "capacity": 30,
        "open_days": "1-5",
        "open_time": time(8, 0),
        "close_time": time(22, 0),
        "rule": "需提前一天预约；使用 GPU 设备须登记；实验室内禁止饮食。",
        "description": "面向深度学习、计算机视觉方向的教学与科研实验。",
        "sort_order": 1,
    },
    {
        "name": "机器人实验室",
        "category": "robot",
        "location": "实验楼 A205",
        "capacity": 20,
        "open_days": "1-6",
        "open_time": time(9, 0),
        "close_time": time(21, 0),
        "rule": "机械臂操作须两人在场；设备使用后需归位并登记状态。",
        "description": "面向机器人控制、运动规划与具身智能实验。",
        "sort_order": 2,
    },
    {
        "name": "云计算实验室",
        "category": "cloud",
        "location": "实验楼 B401",
        "capacity": 40,
        "open_days": "1-7",
        "open_time": time(8, 0),
        "close_time": time(23, 0),
        "rule": "服务器资源按课程优先级分配；禁止擅自更改网络配置。",
        "description": "面向云计算、容器与分布式系统实验。",
        "sort_order": 3,
    },
    {
        "name": "软件工程实验室",
        "category": "se",
        "location": "实验楼 B302",
        "capacity": 50,
        "open_days": "1-5",
        "open_time": time(8, 0),
        "close_time": time(22, 30),
        "rule": "小组预约需注明项目名称；离场前关闭投影与空调。",
        "description": "面向软件项目开发、测试与答辩演练。",
        "sort_order": 4,
    },
]


async def main() -> None:
    async with SessionLocal() as session:
        for item in SEED_LABS:
            # 幂等：名称唯一，已存在就跳过，避免重复插入
            exists = await session.scalar(select(Lab).where(Lab.name == item["name"]))
            if exists is not None:
                print(f"skip  {item['name']}（已存在，id={exists.id}）")
                continue

            session.add(Lab(**item))
            print(f"add   {item['name']}（{item['category']}）")

        await session.commit()

        rows = (await session.scalars(select(Lab).order_by(Lab.sort_order))).all()
        print("\n当前实验室：")
        for row in rows:
            print(
                f"  {row.id:>2}  {row.name:<10} {row.category:<6} "
                f"容量 {row.capacity:<3} 周{row.open_days} "
                f"{row.open_time.strftime('%H:%M')}-{row.close_time.strftime('%H:%M')} {row.status}"
            )

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
