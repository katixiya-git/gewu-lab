import os
import struct

import pytest
from redis.asyncio import Redis

from app.knowledge.chunking import Chunk
from app.knowledge.store import RedisKbStore

URL = os.getenv("GEWU_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未设置 GEWU_TEST_REDIS_URL")


def _vec(seed: int, dim: int = 1024) -> list[float]:
    return [((seed + i) % 7) / 7.0 for i in range(dim)]


@pytest.fixture
async def store():
    client = Redis.from_url(URL, decode_responses=False)
    s = RedisKbStore(client=client, index_name="idx:gewu_test", prefix="gewu:test:", dim=1024)
    await s.reset()
    yield s
    await s.reset()
    await client.aclose()


async def test_upsert_and_search(store):
    chunks = [
        Chunk("doc", "文档", "预约规则", "预约需提前一天提交", 0),
        Chunk("doc", "文档", "取消规则", "开始前 12 小时可取消", 1),
    ]
    await store.upsert(chunks, [_vec(1), _vec(2)])
    assert await store.count() == 2
    hits = await store.search(_vec(1), top_k=2, min_similarity=0.0)
    assert len(hits) == 2
    assert hits[0]["section"] in {"预约规则", "取消规则"}
    assert "content" in hits[0]


async def test_reset_clears_index(store):
    await store.upsert([Chunk("d", "T", "s", "x", 0)], [_vec(3)])
    await store.reset()
    assert await store.count() == 0


async def test_search_returns_distance_sorted(store):
    chunks = [Chunk("d", "T", "s", "x", i) for i in range(3)]
    await store.upsert(chunks, [_vec(10), _vec(20), _vec(30)])
    hits = await store.search(_vec(20), top_k=3, min_similarity=0.0)
    assert hits[0]["similarity"] >= hits[1]["similarity"] >= hits[2]["similarity"]
