"""LangGraph 对话图：模型 ↔ 工具循环。

这是整个 AI 链路的「大脑」。把一次对话想成一条流水线：用户说一句话，
图里的节点按边一个个跑，跑到没有工具要调了才结束。

本例只有两个节点：

- ``agent``：把「系统提示 + 历史消息」发给模型。模型要么直接回答，
  要么发起一次工具调用（比如「帮我查查明天的人工智能实验室」→
  模型自己决定调 ``find_free_slots``）。
- ``tools``：真正执行模型选中的工具，把返回值包成 ``ToolMessage``
  追加到消息列表里，然后回到 ``agent`` 让模型接着说话。

所以「模型思考 → 调工具 → 拿结果 → 再思考」这个循环是靠边来完成的：
``agent`` 有条件边（``tools_condition``）判断最后一条 AI 消息里有没有
``tool_calls``——有就走去 ``tools``，没有就直接结束。
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
    """拼运行时上下文：当前时间与用户姓名。

    为什么每次调用都要现拼：日期、星期这类信息是「会变」的，
    如果写死在系统提示词里，第二天用户问「明天」就算错了。
    ``config`` 由 LangGraph 逐节点传进来，相当于一个随请求流动的
    「背包」，里面放着这次请求的会话 id、用户 id 等信息。
    """
    now = datetime.now(SHANGHAI)
    lines = [f"当前时间：{now:%Y-%m-%d %H:%M}（周{_WEEKDAYS[now.weekday()]}）"]
    user_name = (config.get("configurable") or {}).get("user_name")
    if user_name:
        lines.append(f"当前用户：{user_name}")
    return "\n".join(lines)


def build_agent_graph(checkpointer: BaseCheckpointSaver):
    """编译对话图。

    「编译」是 LangGraph 的术语：把节点、边组装成能直接跑的图对象，
    并把会话存储（checkpointer）挂上去。编译一次、复用多次。

    Args:
        checkpointer: 会话状态存储；生产环境是 Redis，测试可传内存实现。
            它负责每轮结束后把消息列表存下来，下一轮再自动读回来——
            这就是「AI 记得上文」的实现方式，而不是前端每次把历史塞回来。

    Returns:
        CompiledStateGraph: 可直接 ``ainvoke``（一次性拿全部结果）或
        ``astream``（边跑边吐）的图。
    """
    # bind_tools 把 8 个工具的「名字 + 参数 + 说明」告诉模型。
    # 模型本身不会执行函数的，它只是在回复里说「我要调 find_free_slots，
    # 参数是 lab_id=3, day=2026-11-15」，真正执行的是下面的 tools 节点。
    model = get_chat_model().bind_tools(AGENT_TOOLS)

    async def call_model(state: MessagesState, config: RunnableConfig):
        """``agent`` 节点的实现：调一次模型，把回复追加进状态。"""
        # 系统提示词是「每轮现拼」的，不写进 checkpointer：
        # 否则当前时间会随着对话越堆越多，模型会看到十几条互相矛盾的「现在」。
        messages = [SystemMessage(render_system_prompt(_runtime_context(config))), *state["messages"]]
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    # MessagesState 是 LangGraph 内置的状态结构，只有一个 messages 字段；
    # 节点返回 {"messages": [...]} 时会被「追加」而不是覆盖。
    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    # ToolNode 是预置节点：读上一条 AI 消息里的 tool_calls，逐个执行工具，
    # 把结果包成 ToolMessage。工具抛异常时它也会生成一条带 status="error" 的
    # ToolMessage，所以模型能看到「工具失败了」并自己决定怎么回复。
    graph.add_node("tools", ToolNode(AGENT_TOOLS))
    graph.add_edge(START, "agent")
    # 条件边：模型没调工具就走 END，调了工具就去 tools 节点。
    graph.add_conditional_edges("agent", tools_condition)
    # 工具跑完必须回到模型，让模型根据结果组织自然语言回答。
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
