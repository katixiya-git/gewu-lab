"""AI 对话业务：用 LangGraph 图编排「模型 ↔ 工具」循环。

这是 AI 链路的「调度室」：路由层只负责鉴权、限流与把异常映射成 HTTP 状态码；
这里负责真正跑图、收集 token 用量与工具调用记录，并把过程翻译成
前端能理解的事件流。

两个对外方法：

- ``chat()``：等整轮跑完，一次性返回最终回复（简单，但没有流式体验）；
- ``stream_chat()``：边跑边吐事件（用户能看到「正在查空档」这种进度）。

两个方法跑的是同一张图、同一套工具，区别只在「怎么读结果」：
前者用 ``ainvoke``（等全部结束），后者用 ``astream``（来一段读一段）。
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
    """从 LangChain 消息里取纯文本（兼容字符串与内容块列表两种形态）。

    为什么会有两种形态：老模型只返回一个字符串；支持多模态或工具调用的模型
    会返回 ``[{"type": "text", "text": "..."}, {"type": "image_url", ...}]``
    这样的块列表。这里只取文字块，图片/音频一律忽略，反正本项目用不到。
    """
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

    这是一个「防御式解析」：中间任何一步不符合预期就返回 None，
    绝不让一条脏数据把整轮对话搞崩。

    Args:
        message: 工具节点的消息。

    Returns:
        dict | None: 加上 ``conflict`` 标记的卡片数据，可直接下发前端。
    """
    # 只认这一个工具；别的工具（查实验室等）结果里当然没有卡片。
    if getattr(message, "name", None) != BOOKING_TOOL:
        return None
    # ToolNode 执行失败时会生成 status="error" 的消息，内容不是业务 JSON。
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
    # conflict 单独提出来：前端要用它决定提交后的提示语气（普通成功 vs 冲突待协调）。
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
        前缀（``ai_checkpoint_prefix``）则让同一套 Redis 里的其它数据
        （比如别的项目）不会串味。
        """
        return f"{self._settings.ai_checkpoint_prefix}:{user_id}:{session_id or 'default'}"

    def _config(self, user_id: int, user_name: str, thread_id: str) -> dict[str, Any]:
        """组装图的运行配置。

        ``configurable`` 里的东西会随图流动，工具通过 ``RunnableConfig``
        读到 ``user_id``，从而实现「只能查自己的预约」；模型看不到这些值。

        ``recursion_limit`` 是「最多跑几步」的保险丝：模型 ↔ 工具来回算一步，
        给 12 步足够多查几轮，又能防止模型陷入死循环把 token 烧光。
        """
        return {
            "configurable": {"thread_id": thread_id, "user_id": user_id, "user_name": user_name},
            "recursion_limit": 12,
        }

    async def ensure_ready(self) -> None:
        """提前初始化图与 checkpointer；失败时路由可以返回 503/502 而不是半截 SSE。

        为什么要在建流之前做：SSE 一旦开始写响应头就没法改状态码了，
        所以「配置缺失」「Redis 连不上」必须在返回 ``StreamingResponse`` 之前爆出来。
        """
        await self._load_agent()

    async def _load_agent(self):
        """取图，并把「存储侧异常」翻译成统一的 502 错误。"""
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
            # ainvoke 会一直跑到图自己结束：模型不需要工具就直接返回，
            # 需要工具就自动进 tools 节点再回到模型，直到给出最终回答。
            result = await agent.ainvoke(
                {"messages": [HumanMessage(message)]},
                config=self._config(user_id, user_name, thread_id),
            )
        except (APITimeoutError, APIError) as exc:
            raise AiUpstreamError("模型调用超时或失败，请稍后重试") from exc
        except RedisError as exc:
            raise AiUpstreamError("会话存储不可用，请稍后再试") from exc

        # 返回的 messages 是「本次完整上下文」：既有这轮新产生的，也有从
        # checkpoint 读回的历史。最后一条才是模型这轮的最终回答。
        messages = result.get("messages", [])
        reply = _text_of(messages[-1]) if messages else ""

        tools: list[str] = []
        usage = ChatUsage()
        card: dict[str, Any] | None = None
        for item in messages:
            if isinstance(item, AIMessage):
                # 模型的「我要调工具」声明记在这里，前端拿它显示进度。
                for call in item.tool_calls or []:
                    name = call.get("name")
                    if name:
                        tools.append(name)
            elif isinstance(item, ToolMessage):
                found = _card_from_tool(item)
                if found:
                    # 一轮里可能生成多张卡片（用户改了条件重来），只回最后一张
                    card = found
            # token 用量分散在每条消息的 usage_metadata 里，累加才是整轮的账。
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

        这是一个「装饰器式」的异步生成器：它自己不产生内容，只负责给
        ``_stream_events`` 吐出的每条事件加上递增的 ``seq`` 序号。
        拆成两层是为了让编号逻辑只有一个地方，测试也好写。

        Args:
            message: 用户本轮输入。
            user_id: 当前登录用户 id。
            user_name: 当前用户姓名。
            session_id: 前端会话 id。

        Yields:
            dict: ``user_message`` / ``token`` / ``tool_call`` / ``tool`` /
            ``booking_card`` / ``error`` / ``done`` 事件，每条都带从 1 递增的
            ``seq``，前端据此判断有没有漏收事件。
        """
        seq = 0
        async for event in self._stream_events(
            message,
            user_id=user_id,
            user_name=user_name,
            session_id=session_id,
        ):
            seq += 1
            # 用 ``{**event, "seq": seq}`` 生成新 dict，而不是改原对象：
            # 事件可能被上层缓存/广播，就地改会有副作用。
            yield {**event, "seq": seq}

    async def _stream_events(
        self,
        message: str,
        *,
        user_id: int,
        user_name: str,
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """跑图并产出未编号的原始事件，编号工作交给 :meth:`stream_chat`。"""
        agent = await self._load_agent()
        thread_id = self.thread_id(user_id, session_id)

        # 先把用户这条消息回显出去：前端的乐观渲染（发送即显示）据此确认
        # 「这条已经进入服务端会话」，将来接多端时也能按流顺序对齐。
        yield {"type": "user_message", "content": message}

        try:
            # stream_mode 决定「按什么粒度吐」：
            # - "messages"：模型每生成一小段就吐一次（token 流），实现逐字打字效果；
            # - "updates"：每个节点跑完后吐一次（工具被调用/工具结果），
            #   用它来播报「正在查询空档」这类进度。
            async for mode, payload in agent.astream(
                {"messages": [HumanMessage(message)]},
                config=self._config(user_id, user_name, thread_id),
                stream_mode=["messages", "updates"],
            ):
                if mode == "messages":
                    # payload 是 (消息块, 元信息) 二元组；元信息里带节点名，
                    # 这里不关心，只把模型吐的文字转成 token 事件。
                    chunk, _meta = payload
                    if isinstance(chunk, AIMessageChunk):
                        text = _text_of(chunk)
                        if text:
                            yield {"type": "token", "content": text}
                elif mode == "updates":
                    # payload 形如 {"agent": {...}} 或 {"tools": {...}}，
                    # 键是节点名，值是这个节点写回状态的内容。
                    for node, update in (payload or {}).items():
                        if not isinstance(update, dict):
                            continue
                        for item in update.get("messages", []):
                            if node == "agent" and isinstance(item, AIMessage) and item.tool_calls:
                                # 模型决定调工具了：先把名字播出去，前端显示
                                # 「查询空闲时段」之类的进度条。
                                names = [call.get("name") for call in item.tool_calls]
                                yield {
                                    "type": "tool_call",
                                    "names": [name for name in names if name],
                                }
                            elif node == "tools" and isinstance(item, ToolMessage):
                                # 工具执行完了：先报成败，再单独推卡片（如果有）。
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
            # 模型侧异常（超时、限流、鉴权失败）：给出可读提示，本轮就此结束。
            yield {"type": "error", "message": "模型调用超时或失败，请稍后重试"}
        except (RedisError, OSError):
            yield {"type": "error", "message": "会话存储不可用，请稍后再试"}
        except Exception:  # noqa: BLE001 - 兜底：未预期异常也要让前端收到 error + done
            # 注意不要在这里吞掉 CancelledError：它继承 BaseException，
            # 所以客户端断开时这个 except 不会命中，取消仍能正常传播。
            yield {"type": "error", "message": "对话中断，请稍后重试"}

        # done 无条件收尾：前端只有收到它才认为本轮结束，不会一直停在「正在查询」
        yield {"type": "done"}
