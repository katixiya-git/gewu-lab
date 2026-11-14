"""百炼 text-embedding-v3 封装：批量、重试、固定 1024 维。"""

from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from app.ai.client import get_ai_client
from app.config import Settings, get_settings


class EmbeddingError(RuntimeError):
    """嵌入调用失败（网络、限流、返回结构异常）。"""


class DashScopeEmbedder:
    def __init__(self, settings: Settings | None = None, client: AsyncOpenAI | None = None):
        self.settings = settings or get_settings()
        self.client = client or get_ai_client()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """把一批文本转成向量，顺序与输入一致。"""
        if not texts:
            return []
        out: list[list[float]] = []
        batch_size = self.settings.kb_embed_batch_size
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            out.extend(await self._embed_batch(batch))
        return out

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        last: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self.client.embeddings.create(
                    model=self.settings.kb_embedding_model,
                    input=batch,
                    dimensions=self.settings.kb_embedding_dim,
                )
                return self._parse(batch, resp.data)
            except EmbeddingError:
                # 返回结构不对重试也没用，直接让上层拿到明确原因
                raise
            except Exception as exc:  # noqa: BLE001 - 统一转 EmbeddingError 由上层处理
                last = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise EmbeddingError(f"向量化失败：{last}") from last

    def _parse(self, batch: list[str], data) -> list[list[float]]:
        """校验条数与维度，避免把错位的向量写进索引。"""
        vectors = [list(item.embedding) for item in data]
        if len(vectors) != len(batch):
            raise EmbeddingError(f"返回数量不符：{len(vectors)} != {len(batch)}")
        dim = self.settings.kb_embedding_dim
        for index, vector in enumerate(vectors):
            if len(vector) != dim:
                raise EmbeddingError(
                    f"向量维度不符：第 {index} 条为 {len(vector)}，期望 {dim}"
                )
        return vectors
