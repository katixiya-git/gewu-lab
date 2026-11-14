"""SSE 事件流：编号、顺序与中断兜底。

对应 ``backend/app/services/ai_service.py::stream_chat``（事件编号）与
``backend/app/api/routes/ai.py::_heartbeat``（心跳与 SSE 文本格式化）：
对话区里的全部内容（用户消息、增量文本、工具进度、预约卡片）都由同一条
流驱动，所以这里是「流是否可靠」的唯一守门测试。
"""

import asyncio
import json
from types import SimpleNamespace

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from app.api.deps import get_ai_service, get_current_user
from app.api.routes.ai import _heartbeat
from app.api.routes.ai import router as ai_router
from app.services.ai_service import AiService

CARD = {
    "labId": 3,
    "labName": "人工智能实验室",
    "bookingDate": "2026-11-20",
    "startTime": "14:00",
    "endTime": "16:00",
    "peopleCount": 5,
    "bookingType": "personal",
    "bookingTypeText": "个人",
    "purpose": "",
    "contactName": "张三",
    "contactPhone": "13800001111",
    "deviceIds": [],
    "deviceNames": [],
}


class ScriptedAgent:
    """按脚本吐 ``(mode, payload)`` 的假图；脚本里的异常会原样抛出。"""

    def __init__(self, script):
        self._script = script

    async def astream(self, *args, **kwargs):
        for item in self._script:
            if isinstance(item, Exception):
                raise item
            yield item


def _install_agent(monkeypatch, agent):
    async def _load(self):
        return agent

    monkeypatch.setattr(AiService, "_load_agent", _load)


async def _collect(**kwargs):
    return [event async for event in AiService().stream_chat("帮我约个实验室", **kwargs)]


def _token(text):
    return "messages", (AIMessageChunk(content=text), {"langgraph_node": "agent"})


def _tool_call():
    message = AIMessage("", tool_calls=[{"name": "propose_booking", "args": {}, "id": "c1"}])
    return "updates", {"agent": {"messages": [message]}}


def _tool_result(payload, name="propose_booking"):
    message = ToolMessage(
        content=json.dumps(payload, ensure_ascii=False),
        name=name,
        tool_call_id="c1",
    )
    return "updates", {"tools": {"messages": [message]}}


async def test_events_are_numbered_from_one(monkeypatch):
    _install_agent(monkeypatch, ScriptedAgent([_token("你好"), _token("，在的")]))

    events = await _collect(user_id=7, user_name="张三")

    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
    assert events[-1]["type"] == "done"


async def test_events_arrive_in_conversation_order(monkeypatch):
    payload = {"ok": True, "errors": [], "conflict": False, "card": CARD}
    _install_agent(
        monkeypatch,
        ScriptedAgent(
            [
                _token("稍等，我先查一下"),
                _tool_call(),
                _tool_result(payload),
                _token("预约单已生成"),
            ]
        ),
    )

    events = await _collect(user_id=7, user_name="张三")
    types = [event["type"] for event in events]

    # 用户消息先回显，卡片在 done 之前，中间不许有倒序
    assert types[0] == "user_message"
    assert events[0]["content"] == "帮我约个实验室"
    assert types.index("tool_call") < types.index("tool") < types.index("booking_card")
    assert types.index("booking_card") < types.index("done")
    assert types[-1] == "done"


async def test_unexpected_error_still_closes_the_stream(monkeypatch):
    _install_agent(monkeypatch, ScriptedAgent([_token("开始"), RuntimeError("boom")]))

    events = await _collect(user_id=7, user_name="张三")

    types = [event["type"] for event in events]
    # 没有这一层兜底，前端会一直停在「正在查询…」，既收不到 error 也收不到 done
    assert "error" in types
    assert types[-1] == "done"
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))


async def test_heartbeat_fills_silent_gaps():
    async def slow_source():
        await asyncio.sleep(0.05)
        yield {"type": "token", "seq": 1}

    chunks = [chunk async for chunk in _heartbeat(slow_source(), interval=0.01)]

    assert chunks[0] == ": ping\n\n"
    assert chunks[-1].startswith("event: token")
    # 心跳是注释行，不会被当成事件，前端解析器会直接丢弃
    assert all(chunk.startswith(":") for chunk in chunks[:-1])


async def test_heartbeat_leaves_active_stream_alone():
    async def fast_source():
        for index in range(3):
            yield {"type": "token", "seq": index + 1}

    chunks = [chunk async for chunk in _heartbeat(fast_source(), interval=5.0)]

    assert len(chunks) == 3
    assert all(chunk.startswith("event: token") for chunk in chunks)
    assert '"seq": 3' in chunks[-1]
    assert chunks[0].endswith("\n\n")


class StubService:
    """只吐三条事件的假服务，用来验证路由层的 SSE 文本与响应头。"""

    async def ensure_ready(self):
        return None

    async def stream_chat(self, message, *, user_id, user_name, session_id=None):
        yield {"type": "user_message", "content": message, "seq": 1}
        yield {"type": "token", "content": "好的", "seq": 2}
        yield {"type": "done", "seq": 3}


async def test_route_emits_text_event_stream():
    application = FastAPI()
    application.include_router(ai_router)
    application.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, name="张三")
    application.dependency_overrides[get_ai_service] = lambda: StubService()

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/ai/chat/stream", json={"message": "帮我约实验室"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # 这三个头决定了代理不会缓冲、连接不会被当成空闲
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"

    blocks = [block for block in response.text.split("\n\n") if block.strip()]
    assert blocks[0].startswith("event: user_message")
    assert blocks[-1].startswith("event: done")
    assert json.loads(blocks[-1].split("data: ", 1)[1])["seq"] == 3

