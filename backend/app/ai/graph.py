"""LangGraph 对话图：模型 ↔ 工具循环。

状态只有 ``messages``（LangGraph 内置的 ``MessagesState``）：
- ``agent`` 节点把「系统提示 + 历史消息」发给模型；模型要么直接回答，要么发起工具调用；
- ``tools`` 节点执行工具，把结果作为 ``ToolMessage`` 追加回消息列表；
- 条件边根据最后一条 AI 消息里有没有 ``tool_calls`` 决定回到模型还是结束。

系统提示每轮临时拼在消息列表前面，不写进 checkpoint，
这样上下文里的「当前时间/当前用户」不会随着对话越堆越多。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.ai.agent_tools import AGENT_TOOLS
from app.ai.llm import get_chat_model
from app.ai.prompts import render_system_prompt

# 中国没有夏令时，直接用固定 UTC+8，省掉 Windows 上缺失的 tzdata 依赖。
SHANGHAI = timezone(timedelta(hours=8), name="CST")
_WEEKDAYS = "一二三四五六日"


def _runtime_context(config: RunnableConfig) -> str:
    """拼运行时上下文：当前时间与用户姓名。"""
    now = datetime.now(SHANGHAI)
    lines = [f"当前时间：{now:%Y-%m-%d %H:%M}（周{_WEEKDAYS[now.weekday()]}）"]
    user_name = (config.get("configurable") or {}).get("user_name")
    if user_name:
        lines.append(f"当前用户：{user_name}")
    return "\n".join(lines)


def build_agent_graph(checkpointer: BaseCheckpointSaver):
    """编译对话图。

    Args:
        checkpointer: 会话状态存储；生产环境是 Redis，测试可传内存实现。

    Returns:
        CompiledStateGraph: 可直接 ``ainvoke`` / ``astream`` 的图。
    """
    model = get_chat_model().bind_tools(AGENT_TOOLS)

    async def call_model(state: MessagesState, config: RunnableConfig):
        messages = [SystemMessage(render_system_prompt(_runtime_context(config))), *state["messages"]]
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(AGENT_TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
