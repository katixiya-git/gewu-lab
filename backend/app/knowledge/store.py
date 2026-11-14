"""Redis Stack 向量存储：索引生命周期、批量写入、KNN 检索。"""

from __future__ import annotations

import struct

from redis.asyncio import Redis

from app.knowledge.chunking import Chunk


class KbStoreError(RuntimeError):
    """索引不存在、返回结构异常等存储层错误。"""


class RedisKbStore:
    def __init__(self, client: Redis, index_name: str, prefix: str, dim: int = 1024):
        self.client = client
        self.index_name = index_name
        self.prefix = prefix
        self.dim = dim

    # ---- 索引 ----
    async def ensure_index(self) -> None:
        if await self._index_exists():
            return
        await self.client.execute_command(
            "FT.CREATE", self.index_name,
            "ON", "HASH",
            "PREFIX", "1", self.prefix,
            "SCHEMA",
            "doc_id", "TAG",
            "doc_title", "TEXT",
            "section", "TEXT",
            "content", "TEXT",
            "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(self.dim),
            "DISTANCE_METRIC", "COSINE",
        )

    async def _index_exists(self) -> bool:
        try:
            await self.client.execute_command("FT.INFO", self.index_name)
            return True
        except Exception as exc:  # noqa: BLE001 - Redis 用错误串表示不存在
            if _is_missing_index(exc):
                return False
            raise

    async def reset(self) -> None:
        try:
            await self.client.execute_command("FT.DROPINDEX", self.index_name, "DD")
        except Exception as exc:  # noqa: BLE001
            if not _is_missing_index(exc):
                raise
        await self.ensure_index()

    # ---- 写入 ----
    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise KbStoreError(f"块数与向量数不一致：{len(chunks)} != {len(vectors)}")
        await self.ensure_index()
        if not chunks:
            return 0
        pipe = self.client.pipeline(transaction=False)
        for chunk, vector in zip(chunks, vectors, strict=True):
            if len(vector) != self.dim:
                raise KbStoreError(f"向量维度不符：{len(vector)} != {self.dim}")
            key = f"{self.prefix}{chunk.chunk_id}"
            pipe.hset(
                key,
                mapping={
                    "doc_id": chunk.doc_id,
                    "doc_title": chunk.doc_title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "embedding": _pack(vector),
                },
            )
        await pipe.execute()
        return len(chunks)

    async def count(self) -> int:
        try:
            info = await self.client.execute_command("FT.INFO", self.index_name)
        except Exception as exc:  # noqa: BLE001
            if _is_missing_index(exc):
                return 0
            raise
        data = _pairs(info)
        return int(data.get("num_docs", 0))

    # ---- 检索 ----
    async def search(self, vector: list[float], top_k: int, min_similarity: float) -> list[dict]:
        if len(vector) != self.dim:
            raise KbStoreError(f"查询向量维度不符：{len(vector)} != {self.dim}")
        if await self.count() == 0:
            return []
        reply = await self.client.execute_command(
            "FT.SEARCH", self.index_name,
            "*=>[KNN $k @embedding $vec AS score]",
            "PARAMS", "4", "k", str(top_k), "vec", _pack(vector),
            "SORTBY", "score",
            "LIMIT", "0", str(top_k),
            "RETURN", "5", "doc_id", "doc_title", "section", "content", "score",
            "DIALECT", "2",
        )
        hits: list[dict] = []
        for fields in _doc_pairs(reply):
            distance = float(fields.get("score", 1.0))
            similarity = max(0.0, 1.0 - distance)
            if similarity < min_similarity:
                continue
            hits.append(
                {
                    "doc_id": _text(fields.get("doc_id")),
                    "doc_title": _text(fields.get("doc_title")),
                    "section": _text(fields.get("section")),
                    "content": _text(fields.get("content")),
                    "similarity": round(similarity, 4),
                }
            )
        return hits


def _is_missing_index(exc: Exception) -> bool:
    """Redis 各版本对“索引不存在”的报错大小写不一，统一按小写判断。"""
    message = str(exc).lower()
    return "unknown index name" in message or "no such index" in message


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _text(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value or "")


def _pairs(reply: list) -> dict:
    result: dict = {}
    items = reply or []
    for i in range(0, len(items) - 1, 2):
        key = items[i]
        key = key.decode() if isinstance(key, bytes) else str(key)
        result[key] = items[i + 1]
    return result


def _doc_pairs(reply: list) -> list[dict]:
    docs: list[dict] = []
    for i in range(2, len(reply or []), 2):
        raw = reply[i]
        fields: dict = {}
        for j in range(0, len(raw) - 1, 2):
            key = raw[j].decode() if isinstance(raw[j], bytes) else str(raw[j])
            fields[key] = raw[j + 1]
        docs.append(fields)
    return docs
