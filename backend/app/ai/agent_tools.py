"""把内部查询函数包装成 LangChain 工具，供 Agent 调用。

「工具」在 LLM 里的含义：不是模型自己去查数据库，而是我们给它一份
「可调用的函数清单」。模型读到用户问题后，会在回复里说「我要调
``find_free_slots``，参数 lab_id=3、day=2026-11-15」，LangGraph 的
``tools`` 节点照着执行并把结果塞回对话。模型再根据结果组织人话。

所以写一个工具要做三件事，缺一不可：

1. 用 ``@tool`` 装饰，让 LangChain 认识它；
2. **把函数说明写进 docstring**——这段文字会被原样送到模型面前，
   它决定了模型什么时候调、传什么参数。写得含糊模型就会乱调；
3. 参数用类型注解，LangChain 据此生成 JSON Schema 做参数校验。

每个工具自己开一个短会话（``SessionLocal``）——
LangGraph 的工具调用发生在图节点里，拿不到请求的 FastAPI ``Depends``，
所以在工具内部按需取连接最稳妥（用完就关，不占用请求级事务）。

当前登录用户通过 ``RunnableConfig.configurable.user_id`` 注入：
LangChain 会自动把带 ``RunnableConfig`` 注解的参数从工具 schema 里剔除，
模型看不到这个参数，也就无法冒充别人。这是「模型不能提权」的关键设计。
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.ai import tools as domain
from app.db import SessionLocal


def _user_id(config: RunnableConfig) -> int:
    """从工具上下文里取当前用户 id。

    ``config`` 是 LangGraph 逐节点传下来的「背包」，里面装着这次请求的
    会话 id、用户 id 等。取不到就抛异常——宁可失败，也不要拿别人的身份查数据。
    """
    user_id = (config.get("configurable") or {}).get("user_id")
    if not user_id:
        raise ValueError("缺少当前用户，无法执行该操作")
    return int(user_id)


@tool
async def list_labs(keyword: str | None = None) -> list[dict[str, Any]]:
    """列出实验室，可按名称或位置模糊筛选。

    用户问「有哪些实验室」「人工智能相关的实验室」时用。

    Args:
        keyword: 可选，按实验室名称/位置搜索。
    """
    async with SessionLocal() as session:
        return await domain.list_labs(session, keyword)


@tool
async def get_lab(lab_id: int) -> dict[str, Any] | None:
    """查看某个实验室的详细信息（位置/容量/开放时间/规则/设备数量）。

    用户已经指明某间实验室、想了解细节时用；不知道 id 先用 list_labs 查。

    Args:
        lab_id: 实验室 id，可先用 list_labs 查到。
    """
    async with SessionLocal() as session:
        return await domain.get_lab(session, lab_id)


@tool
async def list_devices(lab_id: int | None = None) -> list[dict[str, Any]]:
    """列出设备；传 lab_id 只看某个实验室的设备。

    用户问「有没有 GPU」「3D 打印机在哪」这类问题时用。

    Args:
        lab_id: 可选，实验室 id。
    """
    async with SessionLocal() as session:
        return await domain.list_devices(session, lab_id)


@tool
async def find_free_slots(lab_id: int, day: str) -> dict[str, Any]:
    """查询某实验室某一天的可用时段（30 分钟粒度）。

    用户问「明天下午有空吗」时先换算日期再调；返回的 slots 只有空闲起点，
    具体的起止时间由用户或 ``propose_booking`` 决定。

    Args:
        lab_id: 实验室 id。
        day: 日期，格式 ``YYYY-MM-DD``。
    """
    # 模型只能传字符串，这里自己转成 date；格式不对会抛 ValueError，
    # ToolNode 会把它变成一条错误消息回给模型，模型据此改口重问用户。
    async with SessionLocal() as session:
        return await domain.find_free_slots(session, lab_id, date.fromisoformat(day))


@tool
async def list_my_bookings(config: RunnableConfig, status: str | None = None) -> list[dict[str, Any]]:
    """查询当前用户自己的预约记录。

    注意：只能查「当前登录用户」自己的，查不到别人的——这是工具设计上的
    权限边界，模型没有能力绕过。

    Args:
        status: 可选，按状态过滤：pending/approved/rejected/conflict/cancelled。
    """
    async with SessionLocal() as session:
        return await domain.list_my_bookings(session, _user_id(config), status)


@tool
async def validate_booking_draft(
    lab_id: int,
    day: str,
    start: str,
    end: str,
    people_count: int,
    config: RunnableConfig,
    device_ids: list[int] | None = None,
) -> dict[str, Any]:
    """校验一份预约草稿是否可行（只校验，不创建预约）。

    用户确认草稿后，前端会走正式创建接口；这里只负责把错误和冲突提前查出来。
    用户只是「问问能不能约」时用它，不要用 ``propose_booking``。

    Args:
        lab_id: 实验室 id。
        day: 日期，格式 ``YYYY-MM-DD``。
        start: 开始时间，``HH:MM``。
        end: 结束时间，``HH:MM``。
        people_count: 人数。
        device_ids: 可选，需要的设备 id 列表。
    """
    async with SessionLocal() as session:
        return await domain.validate_booking_draft(
            session,
            _user_id(config),
            lab_id,
            date.fromisoformat(day),
            time.fromisoformat(start),
            time.fromisoformat(end),
            people_count,
            device_ids,
        )


@tool
async def propose_booking(
    lab_id: int,
    day: str,
    start: str,
    end: str,
    people_count: int,
    config: RunnableConfig,
    booking_type: str = "personal",
    purpose: str | None = None,
    device_ids: list[int] | None = None,
) -> dict[str, Any]:
    """生成一张预约卡片给用户确认（不会直接创建预约）。

    用户明确要「预约 / 订 / 占个时段」时用这个工具：先按正式规则校验，
    校验通过就返回一张卡片，前端会把它渲染成带「确认预约」按钮的预约单；
    用户点按钮才真正创建，所以调用后不要声称预约已经创建成功。

    Args:
        lab_id: 实验室 id，先用 list_labs / get_lab 查清楚。
        day: 日期，格式 ``YYYY-MM-DD``。
        start: 开始时间，``HH:MM``，按 30 分钟对齐。
        end: 结束时间，``HH:MM``，与开始时间间隔 30 分钟到 4 小时。
        people_count: 人数，不能超过实验室容量。
        booking_type: 预约类型：personal / group / class，默认 personal。
        purpose: 用途说明，用户说了才填。
        device_ids: 可选，需要的设备 id 列表。
    """
    async with SessionLocal() as session:
        return await domain.propose_booking(
            session,
            _user_id(config),
            lab_id,
            date.fromisoformat(day),
            time.fromisoformat(start),
            time.fromisoformat(end),
            people_count,
            booking_type,
            purpose,
            device_ids,
        )


@tool
async def search_knowledge(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """检索实验室知识库（使用手册/预约与取消规则/设备说明/安全规范）。

    回答规则类问题时优先使用；返回片段带文档名与章节，可用于 [1][2] 标注出处。
    没有命中时返回空列表。

    Args:
        query: 检索问题，用用户的原始问法即可。
        top_k: 返回条数，默认 3，最多 5。
    """
    # 这里再夹一次上下限：模型偶尔会传 0 或 10，别让检索层背这个锅。
    return await domain.search_knowledge(query, min(max(top_k, 1), 5))


# 暴露给 LangGraph 的工具列表；顺序不影响模型选择，但会出现在提示词与
# 工具列表里，所以保持「查数据 → 校验 → 生成卡片 → 查文档」的阅读顺序。
AGENT_TOOLS = [
    list_labs,
    get_lab,
    list_devices,
    find_free_slots,
    list_my_bookings,
    validate_booking_draft,
    propose_booking,
    search_knowledge,
]
