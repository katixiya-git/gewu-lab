"""AI 对话业务：用 LangGraph 图编排「模型 ↔ 工具」循环。

路由层只负责鉴权、限流与把异常映射成 HTTP 状态码；
这里负责真正跑图、收集 token 用量与工具调用记录。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from openai import APIError, APITimeoutError
from redis.exceptions import RedisError

from app.ai.client import AiNotConfiguredError
from app.config import Settings, get_settings
from app.schemas.ai import BookingCard, ChatReply, ChatUsage

# 生成预约卡片的工具名：它成功返回时，本轮对话会多推一个 booking_card 事件
BOOKING_TOOL = "propose_booking"

# 初始化图时可能冒出来的「存储侧」异常，只有这些才映射成 502：
# redis-py 的连接/超时错误、socket 层的 OSError，以及 redisvl 的索引与搜索错误。
# TypeError、ImportError 这类属于代码缺陷，继续冒泡成 500 并留下堆栈，
# 免得把「图装配错了」伪装成「Redis 挂了」。
_STORAGE_ERRORS: tuple[type[BaseException], ...] = (RedisError, OSError)
try:  # redisvl 由 langgraph-checkpoint-redis 引入；万一没装就只按 redis / socket 判断
    from redisvl.exceptions import RedisSearchError
except ImportError:  # pragma: no cover - 正常依赖安装不会走到这里
    pass
else:
    _STORAGE_ERRORS += (RedisSearchError,)


class AiUpstreamError(RuntimeError):
    """模型或会话存储调用失败，路由层映射成 502。"""


def _text_of(message: Any) -> str:
    """从 LangChain 消息里取纯文本（兼容字符串与内容块列表两种形态）。"""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _card_from_tool(message: ToolMessage) -> dict[str, Any] | None:
    """从 ``propose_booking`` 的工具结果里取出预约卡片。

    工具返回的是 ``{"ok", "errors", "conflict", "card"}``，LangGraph 把它
    序列化成 JSON 字符串塞进 ``ToolMessage.content``。只有成功（``ok`` 为真）
    的调用才产生卡片；校验不过或工具抛错时返回 None，让模型去转述原因。

    Args:
        message: 工具节点的消息。

    Returns:
        dict | None: 加上 ``conflict`` 标记的卡片数据，可直接下发前端。
    """
    if getattr(message, "name", None) != BOOKING_TOOL:
        return None
    if getattr(message, "status", "success") == "error":
        return None

    content = message.content
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    card = payload.get("card")
    if not isinstance(card, dict):
        return None
    return {**card, "conflict": bool(payload.get("conflict"))}


class AiService:
    """对话服务：无请求级状态，可被并发复用。"""

    def __init__(self, settings: Settings | None = None) -> None:
        """初始化服务。

        Args:
            settings: 应用配置，默认读取进程单例；测试时可注入。
        """
        self._settings = settings or get_settings()

    def thread_id(self, user_id: int, session_id: str | None) -> str:
        """把用户与会话拼成 checkpoint 的 thread_id。

        前端每个新对话生成一个 sessionId，同一个人开多个对话互不干扰。
        """
        return f"{self._settings.ai_checkpoint_prefix}:{user_id}:{session_id or 'default'}"

    def _config(self, user_id: int, user_name: str, thread_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": thread_id, "user_id": user_id, "user_name": user_name},
            "recursion_limit": 12,
        }

    async def ensure_ready(self) -> None:
        """提前初始化图与 checkpointer；失败时路由可以返回 503/502 而不是半截 SSE。"""
        await self._load_agent()

    async def _load_agent(self):
        # 延迟导入：runtime -> graph -> agent_tools -> app.ai.tools -> app.services 会绕回来
        from app.ai.runtime import get_agent

        try:
            return await get_agent()
        except AiNotConfiguredError:
            raise
        except _STORAGE_ERRORS as exc:
            # 走到这里的都是 checkpointer / Redis 索引的初始化失败：
            # 统一转成 502，避免把连接细节当 500 抛给前端。
            raise AiUpstreamError("会话存储不可用，请稍后再试") from exc

    async def chat(
        self,
        message: str,
        *,
        user_id: int,
        user_name: str,
        session_id: str | None = None,
    ) -> ChatReply:
        """非流式对话：跑完整张图，返回最后一条回复。

        Args:
            message: 用户本轮输入。
            user_id: 当前登录用户 id（注入工具上下文）。
            user_name: 当前用户姓名（写进系统提示）。
            session_id: 前端会话 id；同一 id 共享多轮记忆。

        Returns:
            ChatReply: 回复文本、模型名、token 用量、工具名与会话 id。
        """
        agent = await self._load_agent()
        thread_id = self.thread_id(user_id, session_id)

        try:
            result = await agent.ainvoke(
                {"messages": [HumanMessage(message)]},
                config=self._config(user_id, user_name, thread_id),
            )
        except (APITimeoutError, APIError) as exc:
            raise AiUpstreamError("模型调用超时或失败，请稍后重试") from exc
        except RedisError as exc:
            raise AiUpstreamError("会话存储不可用，请稍后再试") from exc

        messages = result.get("messages", [])
        reply = _text_of(messages[-1]) if messages else ""

        tools: list[str] = []
        usage = ChatUsage()
        card: dict[str, Any] | None = None
        for item in messages:
            if isinstance(item, AIMessage):
                for call in item.tool_calls or []:
                    name = call.get("name")
                    if name:
                        tools.append(name)
            elif isinstance(item, ToolMessage):
                found = _card_from_tool(item)
                if found:
                    # 一轮里可能生成多张卡片（用户改了条件重来），只回最后一张
                    card = found
            meta = getattr(item, "usage_metadata", None)
            if meta:
                usage = ChatUsage(
                    prompt_tokens=usage.prompt_tokens + meta.get("input_tokens", 0),
                    completion_tokens=usage.completion_tokens + meta.get("output_tokens", 0),
                    total_tokens=usage.total_tokens + meta.get("total_tokens", 0),
                )

        return ChatReply(
            reply=reply,
            model=self._settings.ai_model,
            usage=usage,
            tools=tools,
            thread_id=thread_id,
            booking_card=BookingCard.model_validate(card) if card else None,
        )

    async def stream_chat(
        self,
        message: str,
        *,
        user_id: int,
        user_name: str,
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式对话：逐 token 产出事件，同时广播工具调用状态。

        Args:
            message: 用户本轮输入。
            user_id: 当前登录用户 id。
            user_name: 当前用户姓名。
            session_id: 前端会话 id。

        Yields:
            dict: ``token`` / ``tool_call`` / ``tool`` / ``booking_card`` /
            ``error`` / ``done`` 事件。
        """
        agent = await self._load_agent()
        thread_id = self.thread_id(user_id, session_id)

        try:
            async for mode, payload in agent.astream(
                {"messages": [HumanMessage(message)]},
                config=self._config(user_id, user_name, thread_id),
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    chunk, _meta = payload
                    if isinstance(chunk, AIMessageChunk):
                        text = _text_of(chunk)
                        if text:
                            yield {"type": "token", "content": text}
                elif mode == "updates":
                    for node, update in (payload or {}).items():
                        if not isinstance(update, dict):
                            continue
                        for item in update.get("messages", []):
                            if node == "agent" and isinstance(item, AIMessage) and item.tool_calls:
                                names = [call.get("name") for call in item.tool_calls]
                                yield {
                                    "type": "tool_call",
                                    "names": [name for name in names if name],
                                }
                            elif node == "tools" and isinstance(item, ToolMessage):
                                yield {
                                    "type": "tool",
                                    "name": item.name,
                                    "ok": getattr(item, "status", "success") != "error",
                                }
                                card = _card_from_tool(item)
                                if card:
                                    # 卡片要能被路由层直接 json.dumps，这里只放纯 dict
                                    yield {"type": "booking_card", "card": card}
        except (APITimeoutError, APIError):
            yield {"type": "error", "message": "模型调用超时或失败，请稍后重试"}
        except (RedisError, OSError):
            yield {"type": "error", "message": "会话存储不可用，请稍后再试"}

        yield {"type": "done"}
