r"""离线建知识库：读 docs/knowledge/*.md → 切块 → embedding → Redis。

用法（在 backend 下）：

    python -m scripts.build_kb --dry-run
    python -m scripts.build_kb

每次都会全量重建索引（先 drop 再写入），语料只有几十块，几秒完成；
`--rebuild` 仅为兼容旧命令保留，语义与默认一致。
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

from redis.asyncio import Redis

from app.config import get_settings
from app.knowledge.chunking import parse_markdown
from app.knowledge.embedding import DashScopeEmbedder
from app.knowledge.store import RedisKbStore


def load_docs(docs_path: Path) -> list[tuple[str, str, str]]:
    """读取语料目录下全部 .md，返回 (doc_id, 标题, 正文)。

    doc_id 用文件名（不含扩展名），保证稳定；标题优先取正文第一个一级标题，
    没有一级标题时退回文件名。README.md 是目录说明、不是业务语料，跳过。
    """
    docs: list[tuple[str, str, str]] = []
    for path in sorted(docs_path.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        title = path.stem
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        docs.append((path.stem, title, text))
    return docs


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    docs = load_docs(settings.kb_docs_path)
    if not docs:
        raise SystemExit(f"语料目录为空：{settings.kb_docs_path}")

    all_chunks = []
    for doc_id, title, text in docs:
        chunks = parse_markdown(
            text,
            doc_id=doc_id,
            doc_title=title,
            chunk_size=settings.kb_chunk_size,
            overlap=settings.kb_chunk_overlap,
        )
        all_chunks.extend(chunks)
        print(f"{doc_id:24s} {len(chunks):3d} 块")
    total_chars = sum(len(c.content) for c in all_chunks)
    print(f"合计 {len(all_chunks)} 块，约 {total_chars} 字")
    if args.dry_run:
        return

    embedder = DashScopeEmbedder(settings)
    started = time.perf_counter()
    vectors = await embedder.embed([c.content for c in all_chunks])
    print(f"向量化完成：{len(vectors)} 条，{time.perf_counter() - started:.1f}s")

    client = Redis.from_url(settings.redis_url, password=settings.redis_password or None)
    store = RedisKbStore(
        client=client,
        index_name=settings.kb_index_name,
        prefix=settings.kb_key_prefix,
        dim=settings.kb_embedding_dim,
    )
    try:
        # 全量重建：先删旧索引，避免语料改短后残留旧块
        await store.reset()
        started = time.perf_counter()
        written = await store.upsert(all_chunks, vectors)
        print(
            f"写入 {written} 块，{time.perf_counter() - started:.1f}s，"
            f"索引 {settings.kb_index_name} 当前 {await store.count()} 块"
        )
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="离线构建格物知识库向量索引")
    parser.add_argument("--rebuild", action="store_true", help="兼容保留：当前总是全量重建")
    parser.add_argument("--dry-run", action="store_true", help="只切块统计，不调用模型")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
