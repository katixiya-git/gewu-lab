"""AI 对话接口：非流式与 SSE 流式两种形态，内部都走 LangGraph 图。

SSE（Server-Sent Events）是「服务器单向推送」的协议：连接建好之后，
服务端不断往响应里写一行行文本，浏览器边收边处理，连接保持不断。
格式很简单，每条事件由若干 ``字段: 值`` 行组成，用一个空行收尾::

    event: token
    data: {"type": "token", "content": "你好", "seq": 3}

    （空行 = 这条事件结束，可以派发了）

除了 ``event`` 和 ``data``，冒号开头的行（``: ping``）是注释，浏览器会
直接忽略——我们用它做心跳。

为什么要 SSE 而不是 WebSocket：对话是「一问、慢慢答」的单向流动，
SSE 够用、走普通 HTTP、能自动重连，比 WebSocket 少一整套连接管理。
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_ai_service, get_current_user
from app.core.result import Result
from app.models import User
from app.schemas.ai import ChatReply, ChatRequest
from app.services.ai_service import AiNotConfiguredError, AiService, AiUpstreamError

router = APIRouter(prefix="/api/ai", tags=["ai"])

# 两条事件之间允许的最长静默秒数。工具调用（RAG 检索、库查询）常常十几秒
# 不出 token，中间没有字节流过时反向代理和浏览器都可能把连接判死。
HEARTBEAT_SECONDS = 15.0


def _format_event(event: dict[str, Any]) -> str:
    """把一条事件序列化成 SSE 文本块。

    ``ensure_ascii=False`` 很关键：默认会把中文转成 ``\\u4e2d`` 转义序列，
    体积涨三倍，抓包也看不懂。前端 ``JSON.parse`` 两种都能处理，
    但线上排查还是原文好读。
    """
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event['type']}\ndata: {payload}\n\n"


async def _heartbeat(
    source: AsyncIterator[dict[str, Any]],
    interval: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """把事件流格式化成 SSE 文本，静默超过 ``interval`` 秒就补一条注释心跳。

    注释行（``: ping``）是 SSE 规范里的「忽略」语法，浏览器的 ``EventSource``
    和前端自研解析器都不会把它当成事件，所以不会污染事件序列。

    实现上是「race」：一边等业务层的下一个事件，一边计时；谁先到算谁的。
    如果计时先到，就先写一条心跳、继续等同一个事件（事件不会丢）。

    Args:
        source: 业务层的事件生成器，产出纯 dict。
        interval: 最长静默秒数。

    Yields:
        str: 可直接写进 ``text/event-stream`` 的文本块。
    """
    iterator = source.__aiter__()
    # 提前取第一个事件：这样「第一个事件很慢」的情况也能被心跳覆盖。
    pending = asyncio.ensure_future(anext(iterator))
    try:
        while True:
            # asyncio.wait 只等 timeout 这么久，返回 (已完成, 未完成)。
            # done 为空说明到点了还没新事件——该发心跳了。
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield ": ping\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                # 业务层自然结束（generator 跑完了）
                break
            yield _format_event(event)
            # 取到一条后立刻排下一轮的等待，形成流水线。
            pending = asyncio.ensure_future(anext(iterator))
    finally:
        # 客户端断开时 StreamingResponse 会取消这个生成器，
        # 这里顺手把还在等的事件任务收掉，避免留下悬挂任务。
        # suppress(BaseException) 是因为「取消一个正在取消的任务」会抛
        # CancelledError，而我们正处在收尾阶段，不该被它打断。
        pending.cancel()
        with contextlib.suppress(BaseException):
            await pending


# POST /api/ai/chat AI 对话（非流式）
# 入参：message 本轮输入（1–2000 字）；sessionId 可选会话 id，用于隔离多轮记忆
# 鉴权：需要登录；当前用户 id/姓名注入图上下文（工具按登录人查数据）
# 返回：Result[ChatReply]，含回复文本、模型名、token 用量、调用过的工具、threadId
# 错误：
#   422 INVALID_REQUEST 参数不合法（message 为空/超长）
#   503 AI 未启用或未配置 Key
#   502 模型调用失败或会话存储不可用
@router.post(
    "/chat",
    response_model=Result[ChatReply],
    summary="AI 对话（非流式）",
    description="发送一条消息，服务端用 LangGraph 编排模型与工具，返回最终回复与会话 id。",
)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    service: AiService = Depends(get_ai_service),
) -> Result[ChatReply]:
    """发送一条消息并返回模型回复。

    注意这里把「AI 没配好」和「AI 调用失败」分开映射成 503 / 502：
    前者是运维没配置（修配置就好），后者是外部服务出问题（等一会或查日志），
    前端据此能给出不同提示。
    """
    try:
        reply = await service.chat(
            body.message,
            user_id=current_user.id,
            user_name=current_user.name,
            session_id=body.session_id,
        )
    except AiNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AiUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return Result.ok(reply)


# POST /api/ai/chat/stream AI 对话（SSE 流式）
# 请求体同 /api/ai/chat；响应为 text/event-stream
# 事件：user_message（回显本轮输入）/ token（增量文本）/ tool_call（准备调用哪些工具）
#      / tool（工具执行结果）/ booking_card（预约卡片，data.card 是可直接渲染的预约单）
#      / error / done；每条事件带从 1 递增的 seq，便于前端校验有没有漏收
# 说明：先初始化图与 Redis，失败直接返回 JSON 错误（503/502），不进入半截流；
#      静默超过 HEARTBEAT_SECONDS 会插入 `: ping` 注释行，防止网关掐断长连接
@router.post(
    "/chat/stream",
    summary="AI 对话（SSE 流式）",
    description="发送一条消息，以 SSE 推送增量文本、工具调用状态与预约卡片；事件以 event: 行标注类型。",
    response_class=StreamingResponse,
)
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    service: AiService = Depends(get_ai_service),
) -> StreamingResponse:
    """建立 SSE 连接并持续推送对话事件。"""
    # 这里是「先握手、再开流」：一旦返回 StreamingResponse，状态码就已经发出去了，
    # 之后出任何问题都只能靠流里的 error 事件通知前端，改不了 HTTP 状态。
    try:
        await service.ensure_ready()
    except AiNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AiUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    events = service.stream_chat(
        body.message,
        user_id=current_user.id,
        user_name=current_user.name,
        session_id=body.session_id,
    )

    return StreamingResponse(
        _heartbeat(events),
        media_type="text/event-stream",
        headers={
            # 三个头都是为了「别缓存、别缓冲」。尤其 X-Accel-Buffering：
            # Nginx 默认会把响应攒够一坨再转发，逐字输出就变成「卡 10 秒突然全出来」。
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
