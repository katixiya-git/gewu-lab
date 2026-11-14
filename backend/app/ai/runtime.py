"""Agent 的进程级单例：编译好的图 + Redis checkpoint。

「checkpoint」可以理解成「对话存档」：LangGraph 每跑完一轮，就把这轮
新增的消息存进 Redis；下一轮带着同一个 ``thread_id`` 进来，它先把存档读
回来再继续。所以服务端不需要前端回传历史，也能记住上下文。

为什么单例：``AsyncRedisSaver`` 内部维护连接池与索引初始化，
每次请求都新建会拖慢首 token 并泄漏连接。

为什么懒加载：没配 AI Key 或 Redis 暂时不可用时，应用仍应能启动，
只有真正发起对话的请求才报 503/502。
"""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack

from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from app.ai.client import AiNotConfiguredError
from app.ai.graph import build_agent_graph
from app.config import get_settings

# 三个进程级变量：锁、编译好的图、资源栈。
# 图一旦建好就一直是同一个对象；栈负责「关闭时按相反顺序释放 Redis 连接」。
_lock = asyncio.Lock()
_graph = None
_stack: AsyncExitStack | None = None


async def get_agent():
    """返回编译好的对话图；首次调用时连接 Redis 并建索引。

    这里是典型的「双重检查锁」写法：先用无锁的快速判断挡掉绝大多数请求，
    只有第一次（或重建时）才真的去抢锁、连 Redis。

    Returns:
        CompiledStateGraph: 供 ``ainvoke`` / ``astream`` 使用。

    Raises:
        AiNotConfiguredError: 未启用 AI 或没配 Key。
    """
    global _graph, _stack

    if _graph is not None:
        return _graph

    async with _lock:
        # 抢到锁之后要再判断一次：可能刚才别的请求已经建好了。
        if _graph is not None:
            return _graph

        settings = get_settings()
        if not settings.ai_ready:
            raise AiNotConfiguredError("AI 未启用或未配置 API Key")

        # AsyncExitStack 是「异步版的 with 收纳盒」：把连接交给它保管，
        # 以后 ``aclose()`` 一次就能全部按逆序关掉，不用自己记着关哪个。
        stack = AsyncExitStack()
        try:
            saver = await stack.enter_async_context(
                AsyncRedisSaver.from_conn_string(settings.redis_url)
            )
            # asetup() 会在 Redis 里创建放存档用的索引/键空间，重复调用是幂等的。
            await saver.asetup()
            graph = build_agent_graph(saver)
        except Exception:
            # 初始化失败就把半成品收掉，避免连接悬挂
            await stack.aclose()
            raise

        _stack = stack
        _graph = graph
        return _graph


async def close_agent() -> None:
    """应用关闭时释放 Redis checkpoint 的连接。

    由 ``app/main.py`` 的 lifespan 在退出时调用，属于「优雅关闭」的一环。
    """
    global _graph, _stack

    if _stack is not None:
        await _stack.aclose()
    _stack = None
    _graph = None
