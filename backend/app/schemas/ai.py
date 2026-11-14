"""AI 对话相关的请求 / 响应模型。"""

from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


class ChatMessage(CamelModel):
    """一条对话消息（旧版前端回传历史时使用，现在由服务端 checkpoint 记忆）。"""

    role: Literal["user", "assistant"] = Field(description="消息角色")
    content: str = Field(min_length=1, max_length=4000, description="消息内容")


class ChatRequest(CamelModel):
    """一次对话请求：本轮消息 + 可选的会话 id。"""

    message: str = Field(min_length=1, max_length=2000, description="用户本轮输入")
    session_id: str | None = Field(
        default=None,
        max_length=64,
        description="前端生成的会话 id，用来隔离多轮记忆；不传则用该用户的默认会话",
    )
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="已废弃：历史由服务端按 thread_id 保存，传了也不会重复写入",
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
    tools: list[str] = Field(default_factory=list, description="本轮调用过的工具名")
    thread_id: str = Field(description="会话 id，前端后续请求带上即可续聊")


class ChatStreamEvent(CamelModel):
    """SSE 事件：token / tool_call / tool / error / done。"""

    type: Literal["token", "tool_call", "tool", "error", "done"]
    content: str | None = None
    names: list[str] = Field(default_factory=list)
    name: str | None = None
    ok: bool | None = None
    message: str | None = None
