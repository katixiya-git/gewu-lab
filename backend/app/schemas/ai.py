"""AI 对话相关的请求 / 响应模型。"""

from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


class ChatMessage(CamelModel):
    """一条对话消息（前端回传历史时使用）。"""

    role: Literal["user", "assistant"] = Field(description="消息角色")
    content: str = Field(min_length=1, max_length=4000, description="消息内容")


class ChatRequest(CamelModel):
    """一次对话请求：本轮消息 + 可选的历史消息。"""

    message: str = Field(min_length=1, max_length=2000, description="用户本轮输入")
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="最近的历史消息，按时间正序；服务端会再截断",
    )


class ChatUsage(CamelModel):
    """模型 token 用量，便于排查成本。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatReply(CamelModel):
    """非流式对话的返回值。"""

    reply: str = Field(description="模型回复")
    model: str = Field(description="实际使用的模型")
    usage: ChatUsage = Field(default_factory=ChatUsage, description="token 用量")
