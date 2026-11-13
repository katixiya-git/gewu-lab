"""设备种子数据：4 间实验室共 10 台设备，按「实验室 + 名称」幂等写入。

用法（在 backend 目录下，先执行过 ``python -m scripts.init_db``）：

    python -m scripts.seed_devices
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal, close_db
from app.models import Device, Lab

# 与前端 mock 对齐的设备清单；lab 用名称关联，避免写死 id
SEED_DEVICES = [
    # 人工智能实验室
    {"lab": "人工智能实验室", "name": "GPU 服务器", "model": "NVIDIA A100 × 4", "total_count": 2},
    {"lab": "人工智能实验室", "name": "深度学习工作站", "model": "RTX 4090", "total_count": 4},
    {"lab": "人工智能实验室", "name": "高性能 PC", "model": "i9 / 64G", "total_count": 10},
    # 机器人实验室
    {
        "lab": "机器人实验室",
        "name": "六轴机械臂",
        "model": "UR5",
        "total_count": 2,
        "status": "maintenance",
        "note": "需两人在场",
    },
    {"lab": "机器人实验室", "name": "移动机器人", "model": "TurtleBot4", "total_count": 4},
    {"lab": "机器人实验室", "name": "3D 打印机", "model": "Raise3D Pro3", "total_count": 1},
    # 云计算实验室
    {"lab": "云计算实验室", "name": "服务器机柜", "model": "Dell R750 × 8", "total_count": 4},
    {"lab": "云计算实验室", "name": "云终端", "model": "瘦客户端", "total_count": 40},
    # 软件工程实验室
    {"lab": "软件工程实验室", "name": "一体机", "model": "i7 / 32G", "total_count": 50},
    {"lab": "软件工程实验室", "name": "投影设备", "model": "Epson CB-700U", "total_count": 2},
]


async def seed() -> None:
    """写入设备种子；已存在的（实验室 + 名称）跳过。"""
    async with SessionLocal() as session:
        labs = (await session.scalars(select(Lab))).all()
        lab_ids = {lab.name: lab.id for lab in labs}

        created = 0
        skipped = 0
        for index, item in enumerate(SEED_DEVICES, start=1):
            lab_id = lab_ids.get(item["lab"])
            if lab_id is None:
                print(f"[skip] 实验室不存在：{item['lab']}")
                continue

            exists = await session.scalar(
                select(Device.id).where(Device.lab_id == lab_id, Device.name == item["name"])
            )
            if exists is not None:
                skipped += 1
                continue

            session.add(
                Device(
                    lab_id=lab_id,
                    name=item["name"],
                    model=item.get("model"),
                    total_count=item.get("total_count", 1),
                    status=item.get("status", "normal"),
                    note=item.get("note"),
                    sort_order=index,
                )
            )
            created += 1

        await session.commit()
        print(f"设备种子完成：新增 {created} 台，跳过已存在 {skipped} 台")


async def main() -> None:
    """脚本入口：写入后释放连接池。"""
    try:
        await seed()
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
