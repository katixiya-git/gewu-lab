"""DashScopeEmbedder 单测：全部用假客户端，不触网。"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.knowledge import embedding as embedding_mod
from app.knowledge.embedding import DashScopeEmbedder, EmbeddingError

DIM = 64  # Settings 要求 64 <= kb_embedding_dim <= 4096


class _Item:
    def __init__(self, embedding: list[float]):
        self.embedding = embedding


class _Response:
    def __init__(self, vectors: list[list[float]]):
        self.data = [_Item(vec) for vec in vectors]


class FakeClient:
    """最小异步客户端：只实现 ``embeddings.create``，记录每次调用。"""

    def __init__(self, responder):
        self.calls: list[dict] = []
        self.embeddings = self
        self._responder = responder

    async def create(self, *, model, input, dimensions=None):
        call = {"model": model, "input": list(input), "dimensions": dimensions}
        self.calls.append(call)
        result = self._responder(call)
        if isinstance(result, Exception):
            raise result
        return _Response(result)


def make_settings(**overrides) -> Settings:
    base = {
        "kb_embedding_model": "text-embedding-v3",
        "kb_embedding_dim": DIM,
        "kb_embed_batch_size": 10,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def echo_vectors(call: dict) -> list[list[float]]:
    """用输入文本转浮点做可预测向量：'3' -> [3.0] * DIM。"""
    return [[float(text)] * DIM for text in call["input"]]


def make_embedder(responder=echo_vectors, **settings_overrides):
    client = FakeClient(responder)
    embedder = DashScopeEmbedder(settings=make_settings(**settings_overrides), client=client)
    return embedder, client


class _SleepSpy:
    def __init__(self):
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


async def test_empty_input_returns_empty_without_calling_upstream():
    embedder, client = make_embedder()
    assert await embedder.embed([]) == []
    assert client.calls == []


async def test_single_text_passes_model_and_dimensions():
    embedder, client = make_embedder(responder=lambda call: [[0.5] * DIM])
    vectors = await embedder.embed(["实验室预约"])
    assert len(vectors) == 1
    assert len(vectors[0]) == DIM
    assert client.calls == [
        {"model": "text-embedding-v3", "input": ["实验室预约"], "dimensions": DIM}
    ]


async def test_batches_divide_evenly():
    embedder, client = make_embedder(kb_embed_batch_size=2)
    vectors = await embedder.embed(["0", "1", "2", "3"])
    assert [call["input"] for call in client.calls] == [["0", "1"], ["2", "3"]]
    assert [vec[0] for vec in vectors] == [0.0, 1.0, 2.0, 3.0]


async def test_batches_with_remainder_keep_order():
    embedder, client = make_embedder(kb_embed_batch_size=2)
    vectors = await embedder.embed(["0", "1", "2", "3", "4"])
    assert [call["input"] for call in client.calls] == [["0", "1"], ["2", "3"], ["4"]]
    assert [vec[0] for vec in vectors] == [0.0, 1.0, 2.0, 3.0, 4.0]


async def test_transient_error_is_retried_then_succeeds(monkeypatch):
    sleep = _SleepSpy()
    monkeypatch.setattr(embedding_mod.asyncio, "sleep", sleep)
    attempts = {"n": 0}

    def responder(call):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return RuntimeError("rate limited")
        return echo_vectors(call)

    embedder, client = make_embedder(responder=responder)
    vectors = await embedder.embed(["7"])
    assert attempts["n"] == 2
    assert sleep.delays == [0.5]
    assert vectors == [[7.0] * DIM]


async def test_upstream_error_is_wrapped_after_three_attempts(monkeypatch):
    sleep = _SleepSpy()
    monkeypatch.setattr(embedding_mod.asyncio, "sleep", sleep)
    embedder, client = make_embedder(responder=lambda call: RuntimeError("upstream boom"))

    with pytest.raises(EmbeddingError) as excinfo:
        await embedder.embed(["0"])
    assert "upstream boom" in str(excinfo.value)
    assert "向量化失败" in str(excinfo.value)
    assert len(client.calls) == 3
    assert sleep.delays == [0.5, 1.0]


async def test_response_count_mismatch_raises_embedding_error():
    embedder, _ = make_embedder(responder=lambda call: [[0.0] * DIM])
    with pytest.raises(EmbeddingError, match="返回数量不符"):
        await embedder.embed(["0", "1"])


async def test_vector_dimension_mismatch_raises_embedding_error():
    embedder, _ = make_embedder(responder=lambda call: [[0.0] * (DIM - 1)])
    with pytest.raises(EmbeddingError, match="维度不符"):
        await embedder.embed(["0"])


async def test_falls_back_to_shared_ai_client(monkeypatch):
    fake = FakeClient(echo_vectors)
    monkeypatch.setattr(embedding_mod, "get_ai_client", lambda: fake)
    embedder = DashScopeEmbedder(settings=make_settings())
    assert embedder.client is fake


async def test_falls_back_to_get_settings(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr(embedding_mod, "get_settings", lambda: settings)
    embedder = DashScopeEmbedder(client=FakeClient(echo_vectors))
    assert embedder.settings is settings
