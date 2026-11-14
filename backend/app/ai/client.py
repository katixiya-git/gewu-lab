"""模型客户端：统一构造指向百炼的 OpenAI 兼容客户端。

这个文件只干一件事——产出一个「已经配好地址和 Key」的异步客户端。
业务代码（比如知识库的 embedding）只需要 ``client.xxx``，不用关心
供应商是谁、地址长什么样；将来换供应商只改这里。

不对上层暴露 ``openai`` 的类型细节，业务代码只拿到一个可调用的客户端；
后续换供应商（或加代理）只需要改这里。
"""

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import get_settings


class AiNotConfiguredError(RuntimeError):
    """AI 未启用或未配置 Key 时抛出，路由层会映射成 503。

    为什么要自定义异常：让上层能区分「你没配 Key（配置问题）」
    和「模型挂了（外部服务问题）」，前者回 503，后者回 502。
    """


@lru_cache
def get_ai_client() -> AsyncOpenAI:
    """进程内复用一个异步客户端（内部自带连接池，可并发使用）。

    百炼的 OpenAI 兼容接口与官方 SDK 协议一致，只需要换 ``base_url``；
    ``max_retries`` 交给 SDK 做一次轻量重试，避免网络抖动直接失败。

    注意这是同步函数（不是 ``async def``）：它只构造对象，不发请求，
    所以用 ``@lru_cache`` 缓存完全没问题，第一次调用之后的代价是一次字典查表。
    """
    settings = get_settings()
    if not settings.ai_ready:
        raise AiNotConfiguredError("AI 未启用或未配置 API Key")

    return AsyncOpenAI(
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        timeout=settings.ai_timeout_seconds,
        max_retries=2,
    )
