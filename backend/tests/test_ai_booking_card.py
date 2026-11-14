"""预约卡片：工具组装、SSE 事件与降级路径。

对应 ``backend/app/ai/tools.py::propose_booking`` 与
``backend/app/services/ai_service.py::_card_from_tool``：
卡片只是「待确认的预约单」，真正的创建仍由前端点「确认预约」后
走 ``POST /api/bookings``，所以这层不碰数据库写入。
"""

import json
from datetime import date, time
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage

from app.ai import tools as domain
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


class FakeSession:
    """只实现 ``get`` 的假会话，用来给 propose_booking 取当前用户。"""

    def __init__(self, user):
        self._user = user

    async def get(self, model, pk):
        return self._user


class FakeStreamAgent:
    """假的图：按给定的 updates 依次吐流事件，不需要 Redis 与模型。"""

    def __init__(self, updates):
        self._updates = updates

    async def astream(self, *args, **kwargs):
        for payload in self._updates:
            yield "updates", payload


def _install_agent(monkeypatch, agent):
    async def _load(self):
        return agent

    monkeypatch.setattr(AiService, "_load_agent", _load)


def _tool_message(payload, *, status="success"):
    return ToolMessage(
        content=json.dumps(payload, ensure_ascii=False),
        name="propose_booking",
        tool_call_id="call-1",
        status=status,
    )


async def _collect(service, **kwargs):
    return [event async for event in service.stream_chat("帮我约个实验室", **kwargs)]


async def test_stream_emits_booking_card_after_successful_tool(monkeypatch):
    payload = {"ok": True, "errors": [], "conflict": True, "card": CARD}
    agent = FakeStreamAgent([{"tools": {"messages": [_tool_message(payload)]}}])
    _install_agent(monkeypatch, agent)

    events = await _collect(AiService(), user_id=7, user_name="张三")

    cards = [event for event in events if event["type"] == "booking_card"]
    assert len(cards) == 1
    assert cards[0]["card"]["labId"] == 3
    assert cards[0]["card"]["contactPhone"] == "13800001111"
    # 冲突标记要透传给前端，卡片上才能提示「冲突待协调」
    assert cards[0]["card"]["conflict"] is True
    # 卡片是纯 dict，路由层才能直接 json.dumps
    assert isinstance(cards[0]["card"], dict)
    # 事件都带自增 seq，所以只断言类型，不整体比较 dict
    assert events[-1]["type"] == "done"


async def test_stream_skips_card_when_validation_failed(monkeypatch):
    payload = {"ok": False, "errors": ["人数需在 1–10 之间"], "conflict": False, "card": None}
    agent = FakeStreamAgent([{"tools": {"messages": [_tool_message(payload)]}}])
    _install_agent(monkeypatch, agent)

    events = await _collect(AiService(), user_id=7, user_name="张三")

    assert [event for event in events if event["type"] == "booking_card"] == []
    # 工具事件本身仍然要发，前端据此显示「已查询」
    assert any(event["type"] == "tool" for event in events)


async def test_stream_skips_card_when_tool_raised(monkeypatch):
    message = ToolMessage(
        content="数据库连接失败",
        name="propose_booking",
        tool_call_id="call-1",
        status="error",
    )
    agent = FakeStreamAgent([{"tools": {"messages": [message]}}])
    _install_agent(monkeypatch, agent)

    events = await _collect(AiService(), user_id=7, user_name="张三")

    assert [event for event in events if event["type"] == "booking_card"] == []


async def test_non_stream_reply_carries_booking_card(monkeypatch):
    payload = {"ok": True, "errors": [], "conflict": False, "card": CARD}
    messages = [
        AIMessage(
            "",
            tool_calls=[{"name": "propose_booking", "args": {}, "id": "call-1"}],
        ),
        _tool_message(payload),
        AIMessage("已为你生成预约单，确认无误后点卡片上的「确认预约」提交。"),
    ]
    agent = SimpleNamespace()

    async def _ainvoke(*args, **kwargs):
        return {"messages": messages}

    agent.ainvoke = _ainvoke
    _install_agent(monkeypatch, agent)

    reply = await AiService().chat("帮我约个实验室", user_id=7, user_name="张三")

    assert reply.booking_card is not None
    assert reply.booking_card.lab_id == 3
    assert reply.booking_card.start_time == "14:00"
    assert reply.tools == ["propose_booking"]


async def test_propose_booking_uses_account_contact(monkeypatch):
    async def fake_validate(*args, **kwargs):
        return {
            "ok": True,
            "errors": [],
            "conflict": False,
            "draft": {
                "labId": 3,
                "labName": "人工智能实验室",
                "bookingDate": "2026-11-20",
                "startTime": "14:00",
                "endTime": "16:00",
                "peopleCount": 5,
                "deviceIds": [],
                "deviceNames": [],
            },
        }

    monkeypatch.setattr(domain, "validate_booking_draft", fake_validate)
    user = SimpleNamespace(id=7, name="张三", phone=" 13800001111 ")

    result = await domain.propose_booking(
        FakeSession(user),
        7,
        3,
        date(2026, 11, 20),
        time(14, 0),
        time(16, 0),
        5,
        "weird",
        "  项目讨论  ",
    )

    assert result["ok"] is True
    assert result["card"]["contactName"] == "张三"
    assert result["card"]["contactPhone"] == "13800001111"
    assert result["card"]["purpose"] == "项目讨论"
    # 非法的预约类型回落到个人，避免别处再判一次
    assert result["card"]["bookingType"] == "personal"


async def test_propose_booking_requires_phone(monkeypatch):
    async def fake_validate(*args, **kwargs):
        return {"ok": True, "errors": [], "conflict": False, "draft": {"labId": 3}}

    monkeypatch.setattr(domain, "validate_booking_draft", fake_validate)
    user = SimpleNamespace(id=7, name="李四", phone=None)

    result = await domain.propose_booking(
        FakeSession(user),
        7,
        3,
        date(2026, 11, 20),
        time(14, 0),
        time(16, 0),
        5,
    )

    assert result["ok"] is False
    assert result["card"] is None
    assert "联系电话" in result["errors"][0]


async def test_propose_booking_passes_validation_errors_through(monkeypatch):
    async def fake_validate(*args, **kwargs):
        return {
            "ok": False,
            "errors": ["人数需在 1–10 之间"],
            "conflict": False,
            "draft": {"labId": 3},
        }

    monkeypatch.setattr(domain, "validate_booking_draft", fake_validate)
    user = SimpleNamespace(id=7, name="张三", phone="13800001111")

    result = await domain.propose_booking(
        FakeSession(user),
        7,
        3,
        date(2026, 11, 20),
        time(14, 0),
        time(16, 0),
        99,
    )

    assert result["ok"] is False
    assert result["errors"] == ["人数需在 1–10 之间"]
    assert result["card"] is None
