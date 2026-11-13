"""数据库基础设施：异步引擎、会话工厂、ORM 基类与生命周期钩子。

- 引擎与会话工厂在模块导入时创建一次，全进程共用
- 每个 HTTP 请求通过 ``get_session`` 拿到独立会话，请求结束自动归还连接
- ``Base`` 统一提供自增主键与创建/更新时间，业务模型只需写自己的字段
"""

from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

# pool_pre_ping：取连接前先 ping，避免 MySQL 8 小时空闲断连后拿到坏连接
# pool_size/max_overflow：常驻 5 个、峰值最多再扩 10 个
engine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,  # 需要看 SQL 时改成 True
)

# 会话工厂（模具）：本身不持有连接，调用它才得到一个 AsyncSession
# expire_on_commit=False：commit 后仍可读取 ORM 属性，避免响应序列化时再查库
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类，自带 id / create_time / update_time。

    MySQL 侧 create_time 由 ``DEFAULT now()`` 填充；update_time 的自动更新
    由 SQLAlchemy 在 UPDATE 语句里带 ``now()`` 实现，手写 SQL 不会触发。
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")

    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )

    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每个请求一个会话，请求结束自动关闭。

    ``async with`` 退出时会 close（连接归还连接池），异常时同样关闭；
    不要在多个请求之间复用同一个会话。
    """
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """启动自检：执行 ``SELECT 1`` 确认数据库可连接。

    只做连通性检查，不建表；建表由 ``scripts/init_db.py`` 负责，
    避免生产启动时意外改结构。
    """
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """应用退出时释放连接池，避免 MySQL 侧残留连接。"""
    await engine.dispose()
