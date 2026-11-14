"""Markdown 切块：按标题分段，段内按段落/滑窗切分。

设计约束：
- 表格与代码块是不可分割的原子块，允许单块超过 chunk_size；
- 每个 chunk 带完整标题路径，检索结果能直接展示出处；
- 纯函数、无 IO，便于单测。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SENTENCE_END = "。！？；.!?;"
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
        return f"{self.doc_id}#{self.index:03d}"


@dataclass
class _Section:
    path: list[str]
    lines: list[str]


def parse_markdown(
    text: str,
    doc_id: str,
    doc_title: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[Chunk]:
    """把一篇 Markdown 切成带标题路径的块。"""
    sections = _split_sections(text)
    chunks: list[Chunk] = []
    for section in sections:
        body = "\n".join(section.lines).strip()
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
                    index=len(chunks),
                )
            )
    return chunks


def _split_sections(text: str) -> list[_Section]:
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []
    current = _Section(path=[], lines=[])
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_code = not in_code
        match = HEADING_RE.match(line) if not in_code else None
        if match:
            if current.lines:
                sections.append(current)
            level = len(match.group(1))
            title = match.group(2)
            stack = [(lv, tt) for lv, tt in stack if lv < level]
            stack.append((level, title))
            current = _Section(path=[tt for _, tt in stack], lines=[])
        else:
            current.lines.append(line)
    if current.lines:
        sections.append(current)
    if not sections and text.strip():
        sections.append(_Section(path=[], lines=text.splitlines()))
    return sections


def _split_body(body: str, chunk_size: int, overlap: int) -> list[str]:
    blocks = _blocks(body)
    pieces: list[str] = []
    buffer = ""
    for block in blocks:
        atomic = block.startswith("|") or block.startswith("```")
        if atomic and len(block) >= chunk_size:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            pieces.append(block)
            continue
        candidate = f"{buffer}\n\n{block}".strip() if buffer else block
        if len(candidate) <= chunk_size:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
            buffer = (_tail(buffer, overlap) + "\n\n" + block).strip()
        else:
            buffer = block
        if len(buffer) > chunk_size:
            hard = _hard_split(buffer, chunk_size, overlap)
            pieces.extend(hard[:-1])
            buffer = hard[-1]
    if buffer.strip():
        if pieces and len(buffer) < MIN_CHUNK:
            pieces[-1] = f"{pieces[-1]}\n\n{buffer}".strip()
        else:
            pieces.append(buffer)
    return pieces


def _blocks(body: str) -> list[str]:
    blocks: list[str] = []
    buffer: list[str] = []
    mode = None  # None / "table" / "code"
    for line in body.splitlines():
        if line.startswith("```"):
            if mode == "code":
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
            blocks.append("\n".join(buffer))
            buffer, mode = [], None
        if not line.strip():
            if buffer:
                blocks.append("\n".join(buffer))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        blocks.append("\n".join(buffer))
    return blocks


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = max(text.rfind(ch, start, end) for ch in SENTENCE_END)
            if cut > start + size // 2:
                end = cut + 1
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in pieces if p]


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    return text[-overlap:]
