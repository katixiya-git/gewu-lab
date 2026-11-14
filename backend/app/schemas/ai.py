"""AI 对话相关的请求 / 响应模型。"""

from datetime import date
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


class BookingCard(CamelModel):
    """一张待用户确认的预约卡片。

    模型调用 ``propose_booking`` 成功后由服务端下发给前端，字段与
    ``BookingCreateRequest`` 对齐，点「确认预约」时原样提给 ``POST /api/bookings``。
    """

    lab_id: int = Field(description="实验室 id")
    lab_name: str = Field(description="实验室名称")
    booking_date: date = Field(description="预约日期")
    start_time: str = Field(description="开始时间 HH:MM")
    end_time: str = Field(description="结束时间 HH:MM")
    people_count: int = Field(description="人数")
    booking_type: str = Field(default="personal", description="personal / group / class")
    booking_type_text: str = Field(default="", description="类型的中文文案")
    purpose: str | None = Field(default=None, description="用途说明，可空")
    contact_name: str = Field(description="联系人，取当前账号姓名")
    contact_phone: str = Field(description="联系电话，取当前账号手机号")
    device_ids: list[int] = Field(default_factory=list, description="需要的设备 id")
    device_names: list[str] = Field(default_factory=list, description="设备名称，仅用于展示")
    conflict: bool = Field(
        default=False,
        description="与其他人已通过的预约撞车时提交会落为「冲突待协调」",
    )


class ChatReply(CamelModel):
    """非流式对话的返回值。"""

    reply: str = Field(description="模型回复")
    model: str = Field(description="实际使用的模型")
    usage: ChatUsage = Field(default_factory=ChatUsage, description="token 用量")
    tools: list[str] = Field(default_factory=list, description="本轮调用过的工具名")
    thread_id: str = Field(description="会话 id，前端后续请求带上即可续聊")
    booking_card: BookingCard | None = Field(
        default=None,
        description="本轮生成的预约卡片；没有则说明模型没走预约流程",
    )


class ChatStreamEvent(CamelModel):
    """SSE 事件：user_message / token / tool_call / tool / booking_card / error / done。

    路由层是直接把 dict ``json.dumps`` 下发的，不走这个模型；它只用于说明
    事件字段，免得前后端各自记一份。
    """

    type: Literal["user_message", "token", "tool_call", "tool", "booking_card", "error", "done"]
    seq: int = Field(default=0, description="事件序号，从 1 递增；跳号说明中间有事件没收到")
    content: str | None = None
    names: list[str] = Field(default_factory=list)
    name: str | None = None
    ok: bool | None = None
    message: str | None = None
    card: BookingCard | None = Field(
        default=None,
        description="type=booking_card 时下发的预约卡片",
    )
