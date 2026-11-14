"""知识库检索服务与接口单测：全部用 FakeEmbedder / FakeStore，不连真实 Redis 与外网。"""

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.ai.client import AiNotConfiguredError
from app.api.deps import get_current_user, get_knowledge_service
from app.api.routes.knowledge import router as knowledge_router
from app.config import Settings
from app.core.exceptions import register_exception_handlers
from app.knowledge.embedding import EmbeddingError
from app.schemas.knowledge import KnowledgeHitOut
from app.services.knowledge_service import IndexEmptyError, KnowledgeService, get_kb_store


class FakeEmbedder:
    async def embed(self, texts):
        self.last_texts = list(texts)
        return [[1.0] + [0.0] * 1023 for _ in texts]


class FakeStore:
    def __init__(self, count=2):
        self._count = count
        self.last_query = None

    async def count(self):
        return self._count

    async def search(self, vector, top_k, min_similarity):
        self.last_query = (top_k, min_similarity)
        return [{"doc_id": "d", "doc_title": "T", "section": "s", "content": "c", "similarity": 0.9}]


# ---- 服务层 ----


async def test_search_returns_hits():
    service = KnowledgeService(embedder=FakeEmbedder(), store=FakeStore())
    hits = await service.search("预约规则", top_k=3)
    assert hits[0].section == "s"
    assert hits[0].similarity == 0.9


async def test_empty_index_raises():
    service = KnowledgeService(embedder=FakeEmbedder(), store=FakeStore(count=0))
    with pytest.raises(IndexEmptyError):
        await service.search("预约规则")


async def test_embedding_failure_is_wrapped():
    class BadEmbedder:
        async def embed(self, texts):
            raise EmbeddingError("boom")

    service = KnowledgeService(embedder=BadEmbedder(), store=FakeStore())
    with pytest.raises(EmbeddingError):
        await service.search("预约规则")


async def test_search_uses_settings_and_explicit_top_k():
    embedder = FakeEmbedder()
    store = FakeStore()
    service = KnowledgeService(
        embedder=embedder,
        store=store,
        settings=Settings(kb_top_k=7, kb_min_similarity=0.35),
    )

    await service.search("预约规则")
    assert store.last_query == (7, 0.35)
    assert embedder.last_texts == ["预约规则"]

    await service.search("预约规则", top_k=2)
    assert store.last_query == (2, 0.35)


def test_default_store_is_process_singleton():
    assert get_kb_store() is get_kb_store()
    service = KnowledgeService(embedder=FakeEmbedder())
    assert service.store is get_kb_store()


def test_dependency_returns_cached_service(monkeypatch):
    import app.api.deps as deps_module

    created = []

    class StubService:
        def __init__(self):
            created.append(self)

    monkeypatch.setattr(deps_module, "KnowledgeService", StubService)
    deps_module.get_knowledge_service.cache_clear()
    try:
        first = deps_module.get_knowledge_service()
        second = deps_module.get_knowledge_service()
    finally:
        deps_module.get_knowledge_service.cache_clear()

    assert first is second
    assert created == [first]


def test_dependency_maps_missing_ai_key_to_503(monkeypatch):
    import app.api.deps as deps_module

    class MissingKeyService:
        def __init__(self):
            raise AiNotConfiguredError("AI 未启用或未配置 API Key")

    monkeypatch.setattr(deps_module, "KnowledgeService", MissingKeyService)
    deps_module.get_knowledge_service.cache_clear()
    try:
        with pytest.raises(HTTPException) as info:
            deps_module.get_knowledge_service()
    finally:
        deps_module.get_knowledge_service.cache_clear()

    assert info.value.status_code == 503
    assert "AI 未配置" in info.value.detail


# ---- 路由层 ----


class _FakeUser:
    name = "测试用户"


class StubSearchService:
    def __init__(self, hits=None, error=None):
        self._hits = hits or []
        self._error = error
        self.calls = []

    async def search(self, query, top_k=None):
        self.calls.append((query, top_k))
        if self._error is not None:
            raise self._error
        return self._hits


HIT = KnowledgeHitOut(
    doc_id="doc-1",
    doc_title="实验室使用手册",
    section="四间实验室 > 人工智能实验室",
    content="需提前一天预约",
    similarity=0.71,
)


@pytest.fixture(autouse=True)
def _clear_store_cache():
    """每个用例前后清掉进程级 store，避免测试之间串缓存。"""
    get_kb_store.cache_clear()
    yield
    get_kb_store.cache_clear()


@pytest.fixture
def api() -> FastAPI:
    """只挂知识库路由 + 全局异常处理器，避开真实数据库/Redis。"""
    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(knowledge_router)
    application.dependency_overrides[get_current_user] = lambda: _FakeUser()
    return application


@pytest.fixture
async def client(api):
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def validation_api(api) -> FastAPI:
    """请求体校验类用例专用：先把知识库服务顶成桩，屏蔽环境差异。

    FastAPI 的处理顺序是「先解依赖，再校验请求体」。机器上没有配置 AI Key
    时（例如 CI 环境没有 .env），``get_knowledge_service`` 会先抛 503，
    请求根本走不到请求体校验，断言 422 的用例就会假失败。
    这里把依赖换成桩，让用例只关心校验规则本身。
    """
    api.dependency_overrides[get_knowledge_service] = lambda: StubSearchService()
    return api


async def test_route_search_returns_result_envelope(api, client):
    service = StubSearchService([HIT])
    api.dependency_overrides[get_knowledge_service] = lambda: service

    resp = await client.post("/api/knowledge/search", json={"query": "预约规则", "topK": 3})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["message"] == "success"
    assert body["data"][0]["docTitle"] == "实验室使用手册"
    assert body["data"][0]["section"] == "四间实验室 > 人工智能实验室"
    assert body["data"][0]["similarity"] == 0.71
    assert service.calls == [("预约规则", 3)]


async def test_route_empty_index_maps_to_503_envelope(api, client):
    error = IndexEmptyError("知识库为空，请先运行 scripts.build_kb")
    api.dependency_overrides[get_knowledge_service] = lambda: StubSearchService(error=error)

    resp = await client.post("/api/knowledge/search", json={"query": "预约规则"})

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == 503
    assert body["data"] is None
    assert "知识库为空" in body["message"]


async def test_route_embedding_error_maps_to_502_envelope(api, client):
    api.dependency_overrides[get_knowledge_service] = lambda: StubSearchService(
        error=EmbeddingError("boom")
    )

    resp = await client.post("/api/knowledge/search", json={"query": "预约规则"})

    assert resp.status_code == 502
    body = resp.json()
    assert body["code"] == 502
    assert body["data"] is None
    assert body["message"] == "检索服务暂时不可用"


async def test_route_rejects_empty_query(validation_api, client):
    resp = await client.post("/api/knowledge/search", json={"query": ""})

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 422
    # 全局校验错误格式化会过滤 loc 里的 query（本意是 query 参数前缀），
    # 这里只断言中文原因，不强制带字段名
    assert "长度不能少于 1 个字符" in body["message"]


async def test_route_rejects_top_k_over_limit(validation_api, client):
    resp = await client.post("/api/knowledge/search", json={"query": "预约规则", "topK": 50})

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 422
    assert "topK" in body["message"]
    assert "10" in body["message"]


async def test_route_requires_login():
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.core.exceptions import register_exception_handlers
    from app.api.routes.knowledge import router

    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        resp = await ac.post("/api/knowledge/search", json={"query": "预约规则"})

    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 401
    assert "登录" in body["message"]


@pytest.mark.parametrize("top_k", [0, 11])
async def test_route_rejects_top_k_out_of_range(validation_api, client, top_k):
    resp = await client.post("/api/knowledge/search", json={"query": "预约规则", "topK": top_k})

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 422
    assert "topK" in body["message"]


async def test_route_uses_default_top_k_when_omitted(api, client):
    service = StubSearchService([HIT])
    api.dependency_overrides[get_knowledge_service] = lambda: service

    resp = await client.post("/api/knowledge/search", json={"query": "预约规则"})

    assert resp.status_code == 200
    assert service.calls == [("预约规则", None)]


async def test_search_treats_zero_top_k_as_explicit():
    store = FakeStore()
    service = KnowledgeService(
        embedder=FakeEmbedder(), store=store, settings=Settings(kb_top_k=7, kb_min_similarity=0.2)
    )

    await service.search("预约规则", top_k=0)

    assert store.last_query == (0, 0.2)


async def test_route_redis_error_maps_to_503(api, client):
    from redis.exceptions import ConnectionError as RedisConnectionError

    api.dependency_overrides[get_knowledge_service] = lambda: StubSearchService(
        error=RedisConnectionError("boom")
    )

    resp = await client.post("/api/knowledge/search", json={"query": "预约规则"})

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == 503
    assert "知识库暂时不可用" in body["message"]
