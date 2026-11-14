"""百炼 text-embedding-v3 封装：批量、重试、固定 1024 维。

导读：这是 RAG 链路的第二步。上游是 chunking 切好的块，下游是 store 里的
向量索引。
- embedding（嵌入）：把一段文字交给模型，换成一串固定长度的小数（这里
  1024 个）。意思越接近的文字，这两串数字的「方向」越接近，于是距离就能
  当作语义相似度用；
- 向量：就是这串数字，单看某一维（第 7 个数是 0.13）毫无意义，只有整串
  一起比才有意义；所以它对人不可读，只能交给机器算距离；
- 为什么批量：接口按调用次数计费、耗时也按次数算，一次发 10 条远快于发
  10 次；但这里串行发批，不并发——块数只有几十，串行够快也不会撞限流；
- 为什么校验维度：向量库的索引在建索引时就写死了维度，长度不对根本插不
  进去，所以宁可当场报错，也不让错位的数据混进索引。
"""

from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from app.ai.client import get_ai_client
from app.config import Settings, get_settings


class EmbeddingError(RuntimeError):
    """嵌入调用失败（网络、限流、返回结构异常）。"""


class DashScopeEmbedder:
    def __init__(self, settings: Settings | None = None, client: AsyncOpenAI | None = None):
        # client 可注入是给测试用的：换成假客户端就不会真的发网络请求
        self.settings = settings or get_settings()
        self.client = client or get_ai_client()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """把一批文本转成向量，顺序与输入一致。"""
        # 空列表直接返回，省掉一次没有意义的网络调用
        if not texts:
            return []
        out: list[list[float]] = []
        batch_size = self.settings.kb_embed_batch_size
        # 按 batch_size 切片逐批发送，用 extend 拼接即可保持「顺序与输入一致」
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            out.extend(await self._embed_batch(batch))
        return out

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        # 网络抖动、限流这类异常重试往往就过了，因此最多试 3 次，
        # 退避时间 0.5s、1.0s 递增；返回结构错则不重试（见下面的分支）
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
        # 条数不符说明有块没拿到向量；继续往下走会让块与向量整体错位，
        # 检索时「内容」和「向量」对不上，比直接报错难查得多
        if len(vectors) != len(batch):
            raise EmbeddingError(f"返回数量不符：{len(vectors)} != {len(batch)}")
        dim = self.settings.kb_embedding_dim
        # 逐条比维度：Redis 里向量字段是定长的，长度不对就写不进索引
        for index, vector in enumerate(vectors):
            if len(vector) != dim:
                raise EmbeddingError(
                    f"向量维度不符：第 {index} 条为 {len(vector)}，期望 {dim}"
                )
        return vectors
