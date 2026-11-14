"""把内部查询函数包装成 LangChain 工具，供 Agent 调用。

每个工具自己开一个短会话（``SessionLocal``）——
LangGraph 的工具调用发生在图节点里，拿不到请求的 FastAPI ``Depends``，
所以在工具内部按需取连接最稳妥。

当前登录用户通过 ``RunnableConfig.configurable.user_id`` 注入：
LangChain 会自动把带 ``RunnableConfig`` 注解的参数从工具 schema 里剔除，
模型看不到这个参数，也就无法冒充别人。
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.ai import tools as domain
from app.db import SessionLocal


def _user_id(config: RunnableConfig) -> int:
    """从工具上下文里取当前用户 id。"""
    user_id = (config.get("configurable") or {}).get("user_id")
    if not user_id:
        raise ValueError("缺少当前用户，无法执行该操作")
    return int(user_id)


@tool
async def list_labs(keyword: str | None = None) -> list[dict[str, Any]]:
    """列出实验室，可按名称或位置模糊筛选。

    Args:
        keyword: 可选，按实验室名称/位置搜索。
    """
    async with SessionLocal() as session:
        return await domain.list_labs(session, keyword)


@tool
async def get_lab(lab_id: int) -> dict[str, Any] | None:
    """查看某个实验室的详细信息（位置/容量/开放时间/规则/设备数量）。

    Args:
        lab_id: 实验室 id，可先用 list_labs 查到。
    """
    async with SessionLocal() as session:
        return await domain.get_lab(session, lab_id)


@tool
async def list_devices(lab_id: int | None = None) -> list[dict[str, Any]]:
    """列出设备；传 lab_id 只看某个实验室的设备。

    Args:
        lab_id: 可选，实验室 id。
    """
    async with SessionLocal() as session:
        return await domain.list_devices(session, lab_id)


@tool
async def find_free_slots(lab_id: int, day: str) -> dict[str, Any]:
    """查询某实验室某一天的可用时段（30 分钟粒度）。

    Args:
        lab_id: 实验室 id。
        day: 日期，格式 ``YYYY-MM-DD``。
    """
    async with SessionLocal() as session:
        return await domain.find_free_slots(session, lab_id, date.fromisoformat(day))


@tool
async def list_my_bookings(config: RunnableConfig, status: str | None = None) -> list[dict[str, Any]]:
    """查询当前用户自己的预约记录。

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
async def search_knowledge(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """检索实验室知识库（使用手册/预约与取消规则/设备说明/安全规范）。

    回答规则类问题时优先使用；返回片段带文档名与章节，可用于 [1][2] 标注出处。
    没有命中时返回空列表。

    Args:
        query: 检索问题，用用户的原始问法即可。
        top_k: 返回条数，默认 3，最多 5。
    """
    return await domain.search_knowledge(query, min(max(top_k, 1), 5))


# 暴露给 LangGraph 的工具列表；顺序不影响模型选择。
AGENT_TOOLS = [
    list_labs,
    get_lab,
    list_devices,
    find_free_slots,
    list_my_bookings,
    validate_booking_draft,
    search_knowledge,
]
