"""Redis Stack 向量存储：索引生命周期、批量写入、KNN 检索。

导读：这是 RAG 链路的第三步。上游是 chunking 切出的块与 embedding 给的
向量，下游是 knowledge_service 与对话里的 search_knowledge 工具。
- Redis Stack：在普通 Redis 上加了一组检索指令（FT.CREATE、FT.SEARCH），
  于是 Redis 可以当向量数据库用；普通 Redis 没有这些指令，会报未知命令；
- 索引（index）：建索引时声明「哪些字段可搜、向量多少维、用什么距离」，
  之后写入的 HASH 只要 key 前缀对得上就被自动收录，不用手动登记；
- HNSW：一种近似最近邻索引，牺牲一点点准确率换来快得多的检索；维度在
  建索引时就定死，写错维度的记录直接插不进去；
- COSINE（余弦距离）：只比两串向量的方向、不管长度，换算成相似度后
  「0 最不像、1 一模一样」；Redis 给的是距离，所以下面自己做了 1 - 距离；
- 为什么用前缀：向量库与聊天记录共用同一个 Redis，靠 gewu:kb: 前缀隔开，
  删索引（DD）时也只删这一片，不会误伤会话数据。
"""

from __future__ import annotations

import struct

from redis.asyncio import Redis

from app.knowledge.chunking import Chunk


class KbStoreError(RuntimeError):
    """索引不存在、返回结构异常等存储层错误。"""


class RedisKbStore:
    def __init__(self, client: Redis, index_name: str, prefix: str, dim: int = 1024):
        # dim 必须与 embedding 的 kb_embedding_dim 一致；它是索引的硬约束，
        # 不是「参考值」——对不上时写入会失败，或者更糟：读出来全错
        self.client = client
        self.index_name = index_name
        self.prefix = prefix
        self.dim = dim

    # ---- 索引 ----
    async def ensure_index(self) -> None:
        if await self._index_exists():
            return
        # FT.CREATE 的参数是「平铺的字符串」，不是关键字参数，坑点有三：
        # - ON HASH：索引的对象是 Redis HASH 结构；
        # - PREFIX 1 <前缀>：只收录这个前缀的 key，那个 1 是「前缀个数」；
        # - SCHEMA 之后每两三个词描述一个字段，顺序敏感，不能随意调整。
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
            # HNSW 后面那个 6 表示「接下来有 6 个算法参数」，必须与后面
            # 成对出现的参数个数严格一致，多一个少一个都会报语法错
            "TYPE", "FLOAT32",
            "DIM", str(self.dim),
            "DISTANCE_METRIC", "COSINE",
        )

    async def _index_exists(self) -> bool:
        try:
            await self.client.execute_command("FT.INFO", self.index_name)
            return True
        except Exception as exc:  # noqa: BLE001 - Redis 用错误串表示不存在
            # FT.INFO 遇到不存在的索引是抛错、不是返回空；这里只吞「索引
            # 不存在」这一种，连接失败等真故障照旧往上抛，免得把连不上
            # 当成「还没建库」而静默重建出一个空索引
            if _is_missing_index(exc):
                return False
            raise

    async def reset(self) -> None:
        # 先删后建：语料可能变短，只做覆盖写会残留上一次的旧块，
        # 检索时就可能命中已经删掉的内容（幽灵结果）
        await self.drop()
        await self.ensure_index()

    async def drop(self) -> None:
        """删除索引及索引下的文档；索引不存在时静默通过。"""
        try:
            # DD = delete documents：连数据一起删。若只给索引名，HASH 会留下，
            # 变成一堆没人管、也不再被检索到的垃圾数据
            await self.client.execute_command("FT.DROPINDEX", self.index_name, "DD")
        except Exception as exc:  # noqa: BLE001
            if not _is_missing_index(exc):
                raise

    # ---- 写入 ----
    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        # 条数不等时，后面 zip 会把多出来的部分静默丢掉，块与向量就此错位
        if len(chunks) != len(vectors):
            raise KbStoreError(f"块数与向量数不一致：{len(chunks)} != {len(vectors)}")
        await self.ensure_index()
        if not chunks:
            return 0
        # pipeline 把几百条 HSET 攒起来一次发出（transaction=False 关掉
        # MULTI/EXEC）：几百次网络往返变成 1 次。这里不需要事务原子性，
        # 只想要吞吐量，所以不付出事务的额外开销
        pipe = self.client.pipeline(transaction=False)
        for chunk, vector in zip(chunks, vectors, strict=True):
            # strict=True 让两个列表长度不等时直接抛错，而不是悄悄截断
            # 再逐条验维度：写进去的维度错了，索引不会报错，但检索会离谱
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
                    # 向量在 Redis 里是二进制块、不是 JSON 数组，要先打包成 bytes
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
        # FT.INFO 返回扁平数组 [键, 值, 键, 值, ...]，先折成字典再取 num_docs
        data = _pairs(info)
        return int(data.get("num_docs", 0))

    # ---- 检索 ----
    async def search(self, vector: list[float], top_k: int, min_similarity: float) -> list[dict]:
        if len(vector) != self.dim:
            raise KbStoreError(f"查询向量维度不符：{len(vector)} != {self.dim}")
        # 索引为空时提前返回：省掉一次注定没有结果的 KNN 计算
        if await self.count() == 0:
            return []
        reply = await self.client.execute_command(
            "FT.SEARCH", self.index_name,
            # 查询串：* 表示不做字段过滤，=>[KNN ...] 才是真正的向量检索；
            # $k 与 $vec 是占位符，实际值走 PARAMS，避免把二进制拼进查询串
            "*=>[KNN $k @embedding $vec AS score]",
            # PARAMS 后面那个 4 是「随后参数个数」：k 与 vec 两组键值共 4 项
            "PARAMS", "4", "k", str(top_k), "vec", _pack(vector),
            "SORTBY", "score",
            "LIMIT", "0", str(top_k),
            # RETURN 后面的 5 同理，是要返回的字段个数
            "RETURN", "5", "doc_id", "doc_title", "section", "content", "score",
            # DIALECT 2 才认识 KNN 这种查询语法，漏掉会报语法错
            "DIALECT", "2",
        )
        hits: list[dict] = []
        for fields in _doc_pairs(reply):
            # 这里的 score 是余弦距离（0 最像、2 最不像），不是相似度；
            # 换成 1 - 距离 的相似度，越接近 1 越相关，也好按阈值过滤
            distance = float(fields.get("score", 1.0))
            # 距离可能大于 1（方向相反），所以夹一下，别出现负数相似度
            similarity = max(0.0, 1.0 - distance)
            # 阈值过滤：宁可少给几个块，也别把毫不相关的内容塞进系统提示词，
            # 那会让模型顺着无关文本答偏
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
    # 只认这两种措辞：其它错误（连不上、权限不足）必须照旧抛出
    message = str(exc).lower()
    return "unknown index name" in message or "no such index" in message


def _pack(vector: list[float]) -> bytes:
    # "<" 表示小端、"f" 表示 32 位浮点；必须与索引声明的 TYPE FLOAT32 一致。
    # 若这里用 64 位，Redis 会把这些字节按 32 位重新解释，向量全乱但不报错
    return struct.pack(f"<{len(vector)}f", *vector)


def _text(value) -> str:
    # 客户端可能是 decode_responses=False，此时回了 bytes，统一转成 str
    return value.decode("utf-8") if isinstance(value, bytes) else str(value or "")


def _pairs(reply: list) -> dict:
    # 把 FT.INFO 的扁平数组按「两两一组」折成字典；-1 是为了不成对时越界
    result: dict = {}
    items = reply or []
    for i in range(0, len(items) - 1, 2):
        key = items[i]
        key = key.decode() if isinstance(key, bytes) else str(key)
        result[key] = items[i + 1]
    return result


def _doc_pairs(reply: list) -> list[dict]:
    """把 FT.SEARCH 的返回摊平成 [{字段: 值}, ...]。"""
    docs: list[dict] = []
    # 返回结构是 [总数, key1, [字段, 值, 字段, 值...], key2, [...], ...]；
    # 所以从下标 2 起、每隔 2 个取一个（跳过 key 本身），再把字段对折成字典
    for i in range(2, len(reply or []), 2):
        raw = reply[i]
        fields: dict = {}
        for j in range(0, len(raw) - 1, 2):
            key = raw[j].decode() if isinstance(raw[j], bytes) else str(raw[j])
            fields[key] = raw[j + 1]
        docs.append(fields)
    return docs
