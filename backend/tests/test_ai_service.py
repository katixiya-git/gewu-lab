"""AiService 的降级映射：存储侧异常转 502，代码缺陷原样冒泡。

对应 ``backend/app/services/ai_service.py::_load_agent``：
初始化图时只有 Redis / socket 层的问题才值得告诉用户「稍后再试」，
装配错误（TypeError、ImportError 等）必须留下堆栈，不能伪装成存储故障。
"""

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redisvl.exceptions import RedisSearchError

from app.ai import runtime
from app.services.ai_service import AiService, AiUpstreamError


@pytest.fixture
def agent_raises(monkeypatch):
    """把 runtime.get_agent 换成一抛异常的桩，模拟初始化失败。"""

    def _install(exc: BaseException) -> None:
        async def _boom():
            raise exc

        monkeypatch.setattr(runtime, "get_agent", _boom)

    return _install


async def test_redis_connection_error_maps_to_upstream_error(agent_raises):
    agent_raises(RedisConnectionError("Error 111 connecting to 127.0.0.1:6379"))

    with pytest.raises(AiUpstreamError) as excinfo:
        await AiService()._load_agent()

    assert "会话存储不可用" in str(excinfo.value)
    # 原始异常要挂在 __cause__ 上，日志里才看得到根因
    assert isinstance(excinfo.value.__cause__, RedisConnectionError)


async def test_redis_timeout_maps_to_upstream_error(agent_raises):
    agent_raises(RedisTimeoutError("Timeout reading from socket"))

    with pytest.raises(AiUpstreamError):
        await AiService()._load_agent()


async def test_redisvl_search_error_maps_to_upstream_error(agent_raises):
    agent_raises(RedisSearchError("Failed to create index idx:gewu_ai"))

    with pytest.raises(AiUpstreamError):
        await AiService()._load_agent()


async def test_socket_error_maps_to_upstream_error(agent_raises):
    agent_raises(OSError("connection reset by peer"))

    with pytest.raises(AiUpstreamError):
        await AiService()._load_agent()


async def test_not_configured_error_is_not_rewritten(agent_raises):
    """没配 Key 是 503 语义，不能被这里的兜底改写成 502。"""
    from app.ai.client import AiNotConfiguredError

    agent_raises(AiNotConfiguredError("AI 未启用或未配置 API Key"))

    with pytest.raises(AiNotConfiguredError):
        await AiService()._load_agent()


async def test_unexpected_error_keeps_original_type(agent_raises):
    """图装配出错属于代码缺陷，应当 500 并保留堆栈。"""
    agent_raises(TypeError("graph compile failed"))

    with pytest.raises(TypeError):
        await AiService()._load_agent()
