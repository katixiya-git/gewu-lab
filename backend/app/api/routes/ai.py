"""AI 对话接口：非流式与 SSE 流式两种形态，内部都走 LangGraph 图。"""

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
    """把一条事件序列化成 SSE 文本块。"""
    payload = json.dumps(event, ensure_ascii=False)
    return f"event: {event['type']}\ndata: {payload}\n\n"


async def _heartbeat(
    source: AsyncIterator[dict[str, Any]],
    interval: float = HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """把事件流格式化成 SSE 文本，静默超过 ``interval`` 秒就补一条注释心跳。

    注释行（``: ping``）是 SSE 规范里的「忽略」语法，浏览器的 ``EventSource``
    和前端自研解析器都不会把它当成事件，所以不会污染事件序列。

    Args:
        source: 业务层的事件生成器，产出纯 dict。
        interval: 最长静默秒数。

    Yields:
        str: 可直接写进 ``text/event-stream`` 的文本块。
    """
    iterator = source.__aiter__()
    pending = asyncio.ensure_future(anext(iterator))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield ": ping\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield _format_event(event)
            pending = asyncio.ensure_future(anext(iterator))
    finally:
        # 客户端断开时 StreamingResponse 会取消这个生成器，
        # 这里顺手把还在等的事件任务收掉，避免留下悬挂任务。
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
    """发送一条消息并返回模型回复。"""
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
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
