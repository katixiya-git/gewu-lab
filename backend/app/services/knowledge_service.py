"""知识库检索服务：把「问题 → 向量 → 最近块」串起来。"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.knowledge.embedding import DashScopeEmbedder
from app.knowledge.store import RedisKbStore
from app.schemas.knowledge import KnowledgeHitOut


class IndexEmptyError(RuntimeError):
    """索引里没有任何块，通常是还没跑 build_kb。"""


class KnowledgeService:
    """检索服务：无请求级状态，可被并发复用。

    默认构造会复用进程级的向量库单例（见 :func:`get_kb_store`），
    不会每个请求都新建 Redis 客户端与连接池。
    """

    def __init__(
        self,
        embedder=None,
        store=None,
        settings: Settings | None = None,
    ) -> None:
        """初始化服务。

        Args:
            embedder: 向量化实现，默认百炼 ``DashScopeEmbedder``；测试可注入假实现。
            store: 向量库实现，默认复用进程单例 ``get_kb_store()``；测试可注入假实现。
            settings: 应用配置，默认读取进程单例；测试可注入以控制 topK/阈值。
        """
        self.settings = settings or get_settings()
        self.embedder = embedder or DashScopeEmbedder(self.settings)
        self.store = store or get_kb_store()

    async def search(self, query: str, top_k: int | None = None) -> list[KnowledgeHitOut]:
        """检索与问题最相关的若干片段。

        Args:
            query: 用户问题。
            top_k: 返回条数；为空时用配置里的 ``kb_top_k``。

        Returns:
            list[KnowledgeHitOut]: 按相似度倒序的片段，可能为空。

        Raises:
            IndexEmptyError: 索引里没有任何块（还没建库或索引名配错）。
            app.knowledge.embedding.EmbeddingError: 向量化失败。
        """
        if await self.store.count() == 0:
            raise IndexEmptyError("知识库为空，请先运行 scripts.build_kb")
        vectors = await self.embedder.embed([query])
        hits = await self.store.search(
            vectors[0],
            top_k=self.settings.kb_top_k if top_k is None else top_k,
            min_similarity=self.settings.kb_min_similarity,
        )
        return [KnowledgeHitOut(**hit) for hit in hits]


@lru_cache
def get_kb_store() -> RedisKbStore:
    """进程内复用一个 ``RedisKbStore``（含 Redis 客户端与连接池）。

    ``redis.asyncio.Redis`` 自带连接池、可并发复用；如果每次
    ``KnowledgeService()`` 都 ``Redis.from_url`` 一次，请求越密集连接与
    文件句柄泄漏越严重（Windows 下尤其明显），因此这里用 ``lru_cache``
    做进程单例。测试需要替换时注入 ``store=`` 或调用 ``.cache_clear()``。
    """
    from redis.asyncio import Redis

    settings = get_settings()
    client = Redis.from_url(settings.redis_url, password=settings.redis_password or None)
    return RedisKbStore(
        client=client,
        index_name=settings.kb_index_name,
        prefix=settings.kb_key_prefix,
        dim=settings.kb_embedding_dim,
    )
