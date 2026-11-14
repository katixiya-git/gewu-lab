"""Markdown 切块：按标题分段，段内按段落/滑窗切分。

导读：这是 RAG（检索增强生成）链路的第一步——先从文档里查出相关片段，
再让模型照着这些片段回答。上游是 docs/knowledge/ 下的 Markdown 手册，
下游是 embedding（嵌入：把一段文字变成一串小数）与向量库。
- 为什么要切：整篇文档既塞不进提示词，也没法只用一个向量代表，只能切成
  小段、每段单独转向量；检索命中的就是这些段，所以切法直接决定准不准；
- 为什么约 500 字：太短缺上下文。太长则一段里主题混杂、向量被平均掉；
- 为什么重叠：答案可能正好落在切口上，相邻块共享几十字，两边都能命中；
- 标题路径：每块记下自己属于哪一章哪一节，检索结果能显示出处。

设计约束：
- 表格与代码块是不可分割的原子块，允许单块超过 chunk_size；
- 每个 chunk 带完整标题路径，检索结果能直接展示出处；
- 纯函数、无 IO，便于单测。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 句末标点：超长段落硬切时优先在这些字符后面下刀，别把一句话劈成两半
SENTENCE_END = "。！？；.!?;"
# 尾巴短于这个字数就不再单独成块，直接并回上一块，免得出十几个字的碎片块
MIN_CHUNK = 40


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    doc_title: str
    section: str
    content: str
    index: int

    @property
    def chunk_id(self) -> str:
        # 补零到三位：同一文档内块序号定长，id 可读也能稳定排序。
        # 这个 id 就是 Redis 的主键后缀，同一篇文档重跑建库得到的 id 不变。
        return f"{self.doc_id}#{self.index:03d}"


@dataclass
class _Section:
    # path 是标题栈展开的结果，如 ["实验室手册", "预约规则", "取消规则"]
    path: list[str]
    lines: list[str]


def parse_markdown(
    text: str,
    doc_id: str,
    doc_title: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[Chunk]:
    """把一篇 Markdown 切成带标题路径的块。

    chunk_size 与 overlap 都按「字符」计，不是 token 数；中文里一个汉字算
    一个字符，500 字大致对应几百 token，正好在模型与向量的舒适区间内。
    """
    sections = _split_sections(text)
    chunks: list[Chunk] = []
    for section in sections:
        body = "\n".join(section.lines).strip()
        # 只有标题、没有正文的章节（例如纯目录页）不产块，否则会得到空块
        if not body:
            continue
        path = " > ".join(section.path)
        for piece in _split_body(body, chunk_size, overlap):
            content = piece.strip()
            if not content:
                continue
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    doc_title=doc_title,
                    section=path,
                    content=content,
                    # 序号取「已收集的块数」，天然单调递增，重复建库也不会变
                    index=len(chunks),
                )
            )
    return chunks


def _split_sections(text: str) -> list[_Section]:
    sections: list[_Section] = []
    # stack 模拟标题栈：遇到 ### 时把层级 >= 3 的旧标题弹掉，剩下的就是祖先
    stack: list[tuple[int, str]] = []
    current = _Section(path=[], lines=[])
    # in_code 用来跳过代码块里的 # 行：那些是注释，不是 Markdown 标题
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_code = not in_code
        match = HEADING_RE.match(line) if not in_code else None
        if match:
            # 遇到新标题，说明上一节到此为止，先把它的正文收进 sections
            if current.lines:
                sections.append(current)
            level = len(match.group(1))
            title = match.group(2)
            # 只保留层级更浅的祖先标题，再把当前标题压栈
            stack = [(lv, tt) for lv, tt in stack if lv < level]
            stack.append((level, title))
            current = _Section(path=[tt for _, tt in stack], lines=[])
        else:
            current.lines.append(line)
    if current.lines:
        sections.append(current)
    # 整篇没有标题（比如纯文本说明）时退化成「一个没有路径的章节」
    if not sections and text.strip():
        sections.append(_Section(path=[], lines=text.splitlines()))
    return sections


def _split_body(body: str, chunk_size: int, overlap: int) -> list[str]:
    """把一节正文切成若干块：先按空行切自然段，再按长度合并/滑窗。"""
    blocks = _blocks(body)
    pieces: list[str] = []
    # buffer 是「正在攒的那一块」；攒到接近 chunk_size 或撞上原子块时才 flush
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer.strip():
            pieces.append(buffer.strip())
        buffer = ""

    for block in blocks:
        atomic = block.startswith("|") or block.startswith("```")
        if atomic:
            # 原子块永远独立成块：既不在它前面拼正文，也不让 overlap 尾巴
            # 落进来（否则表格/代码会被拦腰切断或复制出残片）。
            flush()
            pieces.append(block.strip())
            continue

        candidate = f"{buffer}\n\n{block}".strip() if buffer else block
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue

        flush()
        # 新块开头带上上一块的尾巴，让跨块的问题仍有上下文可接
        if pieces and not _is_atomic(pieces[-1]):
            buffer = (_tail(pieces[-1], overlap) + "\n\n" + block).strip()
        else:
            buffer = block
        # 单个段落自己就超过 chunk_size（如没有空行的长文）时只能句子级硬切
        if len(buffer) > chunk_size:
            hard = _hard_split(buffer, chunk_size, overlap)
            pieces.extend(hard[:-1])
            buffer = hard[-1]

    if buffer.strip():
        # 收尾：最后剩一小截就并回上一块，减少「十几个字的碎片块」
        if pieces and len(buffer) < MIN_CHUNK and not _is_atomic(pieces[-1]):
            pieces[-1] = f"{pieces[-1]}\n\n{buffer}".strip()
        else:
            pieces.append(buffer.strip())
    return pieces


def _is_atomic(text: str) -> bool:
    # 表格以 | 开头、代码块以 ``` 开头；这两类必须保持完整
    stripped = text.lstrip()
    return stripped.startswith("|") or stripped.startswith("```")


def _blocks(body: str) -> list[str]:
    """把正文切成「段落 / 表格 / 代码块」三类块，后两类不可再分。"""
    blocks: list[str] = []
    buffer: list[str] = []
    # mode 记着当前是否正处在表格或代码块内部——这是跨行的状态，必须显式存
    mode = None  # None / "table" / "code"
    for line in body.splitlines():
        if line.startswith("```"):
            if mode == "code":
                # 闭合围栏：连同开头那行一起交出整个代码块
                buffer.append(line)
                blocks.append("\n".join(buffer))
                buffer, mode = [], None
            else:
                if buffer:
                    blocks.append("\n".join(buffer))
                buffer, mode = [line], "code"
            continue
        if mode == "code":
            buffer.append(line)
            continue
        if line.startswith("|"):
            if mode == "table":
                buffer.append(line)
            else:
                if buffer:
                    blocks.append("\n".join(buffer))
                buffer, mode = [line], "table"
            continue
        if mode == "table":
            # 遇到第一个非 | 的行，表格结束，整表交出
            blocks.append("\n".join(buffer))
            buffer, mode = [], None
        if not line.strip():
            # 空行是段落分隔符：把攒着的段落交出去，下一段另起
            if buffer:
                blocks.append("\n".join(buffer))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        blocks.append("\n".join(buffer))
    return blocks


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    """按字符数硬切（兜底手段），切口优先落在句末标点上。"""
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # 在当前窗口里找最后一个句末标点，找到就提前一点下刀
            cut = max(text.rfind(ch, start, end) for ch in SENTENCE_END)
            # 句号太靠前（切出的块不足半块）就宁可硬切，避免块过短
            if cut > start + size // 2:
                end = cut + 1
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        # 下一窗从 end 往前退 overlap 个字符，让相邻块有重叠内容
        # start + 1 是兜底：即使 overlap 很大也必须前进，否则死循环
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]


def _tail(text: str, overlap: int) -> str:
    # 取最后 overlap 个字符；text 本身比 overlap 短时切片会自动取全部
    if overlap <= 0:
        return ""
    return text[-overlap:]
