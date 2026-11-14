"""LangChain 对话模型：百炼的 OpenAI 兼容接口。

相比裸 ``AsyncOpenAI``，这里用 ``ChatOpenAI`` 是为了直接拿到
``bind_tools`` / ``astream_events`` 等能力，交给 LangGraph 编排。
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.ai.client import AiNotConfiguredError
from app.config import get_settings


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    """进程内复用同一个 ``ChatOpenAI``（内部带 httpx 连接池）。

    Returns:
        ChatOpenAI: 指向百炼兼容接口的对话模型。

    Raises:
        AiNotConfiguredError: 未启用 AI 或没配 Key。
    """
    settings = get_settings()
    if not settings.ai_ready:
        raise AiNotConfiguredError("AI 未启用或未配置 API Key")

    return ChatOpenAI(
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        temperature=settings.ai_temperature,
        timeout=settings.ai_timeout_seconds,
        max_retries=2,
    )
