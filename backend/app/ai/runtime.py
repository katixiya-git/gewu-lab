"""Agent 的进程级单例：编译好的图 + Redis checkpoint。

为什么要单例：``AsyncRedisSaver`` 内部维护连接池与索引初始化，
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

_lock = asyncio.Lock()
_graph = None
_stack: AsyncExitStack | None = None


async def get_agent():
    """返回编译好的对话图；首次调用时连接 Redis 并建索引。

    Returns:
        CompiledStateGraph: 供 ``ainvoke`` / ``astream`` 使用。

    Raises:
        AiNotConfiguredError: 未启用 AI 或没配 Key。
    """
    global _graph, _stack

    if _graph is not None:
        return _graph

    async with _lock:
        if _graph is not None:
            return _graph

        settings = get_settings()
        if not settings.ai_ready:
            raise AiNotConfiguredError("AI 未启用或未配置 API Key")

        stack = AsyncExitStack()
        try:
            saver = await stack.enter_async_context(
                AsyncRedisSaver.from_conn_string(settings.redis_url)
            )
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
    """应用关闭时释放 Redis checkpoint 的连接。"""
    global _graph, _stack

    if _stack is not None:
        await _stack.aclose()
    _stack = None
    _graph = None
