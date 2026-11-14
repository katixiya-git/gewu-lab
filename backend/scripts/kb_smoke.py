"""知识库检索冒烟：固定问题 + top3 + 延迟统计 + top1 稳定性复检。

用法（在 ``backend`` 下）：

    .\\.venv\\Scripts\\python.exe -m scripts.kb_smoke

脚本只读取索引、不写库；每个问题查一次用于输出与延迟统计，再连查一次
比对 top1 的 ``doc_id`` 是否一致（HNSW 检索应为确定性结果）。
"""

from __future__ import annotations

import asyncio
import statistics
import time

from app.knowledge.embedding import DashScopeEmbedder
from app.services.knowledge_service import KnowledgeService

QUESTIONS = [
    "人工智能实验室能容纳多少人",
    "预约需要提前多久提交",
    "取消预约有什么限制",
    "六轴机械臂使用要注意什么",
    "3D 打印机怎么通风",
]


def _top1(hits) -> tuple[str, str] | None:
    """取 top1 的 (doc_id, section)；无结果时返回 None。"""
    if not hits:
        return None
    return hits[0].doc_id, hits[0].section


async def main() -> None:
    service = KnowledgeService(embedder=DashScopeEmbedder())
    print(f"索引：{service.settings.kb_index_name}  块数：{await service.store.count()}")

    latencies: list[float] = []
    first_top1: dict[str, tuple[str, str] | None] = {}
    max_similarity = 0.0

    for question in QUESTIONS:
        started = time.perf_counter()
        hits = await service.search(question, top_k=3)
        elapsed = (time.perf_counter() - started) * 1000
        latencies.append(elapsed)
        first_top1[question] = _top1(hits)
        if hits:
            max_similarity = max(max_similarity, hits[0].similarity)
        print(f"\nQ: {question}  ({elapsed:.0f}ms)")
        for hit in hits:
            print(f"  {hit.similarity:.3f}  {hit.doc_id} / {hit.section}")
            print(f"        {hit.content[:60]}")

    stable = 0
    print("\n稳定性复检（同一问题连查两次，比较 top1 doc_id）")
    for question in QUESTIONS:
        hits = await service.search(question, top_k=3)
        current = _top1(hits)
        first = first_top1[question]
        same = current is not None and first is not None and current[0] == first[0]
        stable += same
        current_doc = current[0] if current else "无结果"
        first_doc = first[0] if first else "无结果"
        print(f"  {'OK  ' if same else 'DIFF'} {question}：首查 {first_doc} → 复查 {current_doc}")

    print(
        f"\n延迟 p50={statistics.median(latencies):.0f}ms  "
        f"max={max(latencies):.0f}ms  min={min(latencies):.0f}ms"
    )
    print(
        f"最高 similarity={max_similarity:.4f}  "
        f"top1 稳定 {stable}/{len(QUESTIONS)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
