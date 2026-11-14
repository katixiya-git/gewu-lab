"""LangChain 对话模型：百炼（阿里云）的 OpenAI 兼容接口。

「OpenAI 兼容」的意思是：百炼的 HTTP 接口和 OpenAI 的协议一模一样，
只是换个地址和 Key（默认地址见 ``settings.ai_base_url``，模型是
``qwen-plus``）。所以我们可以直接用 OpenAI 生态的 SDK。

相比裸 ``AsyncOpenAI``，这里用 ``ChatOpenAI`` 是为了直接拿到
``bind_tools``（告诉模型有哪些工具可调）这类能力，交给 LangGraph 编排。
裸客户端 ``AsyncOpenAI`` 仍然保留在 ``app/ai/client.py``，
知识库的 embedding 调用走的是它。
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.ai.client import AiNotConfiguredError
from app.config import get_settings


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    """进程内复用同一个 ``ChatOpenAI``（内部带 httpx 连接池）。

    ``@lru_cache(maxsize=1)`` 是「全局只建一次」的最简写法：第一次调用时
    构造对象，之后每次调用都返回同一个实例，避免每个请求都新建连接池。

    Returns:
        ChatOpenAI: 指向百炼兼容接口的对话模型。

    Raises:
        AiNotConfiguredError: 未启用 AI 或没配 Key。
    """
    settings = get_settings()
    # ai_ready 是 config.py 里的判断：AI_ENABLED 为真且填了 Key 才算配置好。
    # 早期在这里就报错，而不是等到请求模型时，报错信息更直白。
    if not settings.ai_ready:
        raise AiNotConfiguredError("AI 未启用或未配置 API Key")

    return ChatOpenAI(
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        # 温度越低越稳定，预约场景不需要「创造力」。
        temperature=settings.ai_temperature,
        timeout=settings.ai_timeout_seconds,
        # 网络抖动时的重试次数，交给 SDK 处理，模型层不用自己写循环。
        max_retries=2,
    )
