"""AI 对话业务：用 LangGraph 图编排「模型 ↔ 工具」循环。

路由层只负责鉴权、限流与把异常映射成 HTTP 状态码；
这里负责真正跑图、收集 token 用量与工具调用记录。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from openai import APIError, APITimeoutError
from redis.exceptions import RedisError

from app.ai.client import AiNotConfiguredError
from app.config import Settings, get_settings
from app.schemas.ai import ChatReply, ChatUsage


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
        except (RedisError, OSError) as exc:
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
        for item in messages:
            if isinstance(item, AIMessage):
                for call in item.tool_calls or []:
                    name = call.get("name")
                    if name:
                        tools.append(name)
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
            dict: ``token`` / ``tool_call`` / ``tool`` / ``error`` / ``done`` 事件。
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
        except (APITimeoutError, APIError):
            yield {"type": "error", "message": "模型调用超时或失败，请稍后重试"}
        except (RedisError, OSError):
            yield {"type": "error", "message": "会话存储不可用，请稍后再试"}

        yield {"type": "done"}
