"""AI 对话接口：先提供非流式对话，用于打通模型、提示词与消息链路。

流式接口和 LangGraph 编排会在后续迭代补进来，路径仍然挂在 ``/api/ai`` 下。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_ai_service, get_current_user
from app.core.result import Result
from app.models import User
from app.schemas.ai import ChatReply, ChatRequest
from app.services.ai_service import AiNotConfiguredError, AiService, AiUpstreamError

router = APIRouter(prefix="/api/ai", tags=["ai"])


# POST /api/ai/chat AI 对话（非流式）
# 入参：message 本轮输入（1–2000 字）；history 最近历史（可选，最多 20 条）
# 鉴权：需要登录；当前用户姓名会作为上下文传给模型，便于称呼与定位预约人
# 返回：Result[ChatReply]，含回复文本、实际模型名、token 用量
# 错误：
#   422 INVALID_REQUEST 参数不合法（message 为空/超长、history 超 20 条）
#   503 AI 未启用或未配置 Key
#   502 模型调用失败（超时/限流/上游错误）
@router.post(
    "/chat",
    response_model=Result[ChatReply],
    summary="AI 对话（非流式）",
    description="发送一条消息，返回模型回复；历史消息由调用方回传，服务端按配置截断。",
)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    service: AiService = Depends(get_ai_service),
) -> Result[ChatReply]:
    """发送一条消息并返回模型回复。"""
    try:
        reply = await service.chat(body.message, body.history, current_user.name)
    except AiNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AiUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return Result.ok(reply)
