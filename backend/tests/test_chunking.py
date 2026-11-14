from app.knowledge.chunking import Chunk, parse_markdown


def test_heading_path_is_preserved():
    md = """# 实验室手册

## 预约规则

预约需提前一天。

### 取消规则

开始前 12 小时内需提交取消申请。
"""
    chunks = parse_markdown(md, doc_id="handbook", doc_title="实验室手册")
    sections = [c.section for c in chunks]
    assert any("预约规则" in s and "取消规则" in s for s in sections)
    assert any("12 小时" in c.content for c in chunks)


def test_long_section_is_windowed_without_losing_text():
    md = "## 长文\n\n" + "".join(f"第{i}句内容。" for i in range(300))
    chunks = parse_markdown(md, doc_id="long", doc_title="长文", chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c.content) <= 300 for c in chunks)
    joined = "".join(c.content for c in chunks)
    for i in (0, 100, 299):
        assert f"第{i}句内容。" in joined


def test_table_is_atomic_even_if_larger_than_chunk_size():
    rows = ["| 设备 | 数量 |", "| --- | --- |"] + [f"| 设备{i} | {i} |" for i in range(20)]
    md = "## 设备清单\n\n" + "\n".join(rows)
    chunks = parse_markdown(md, doc_id="table", doc_title="设备", chunk_size=100, overlap=20)
    table_chunks = [c for c in chunks if "设备19" in c.content]
    assert len(table_chunks) == 1
    assert "设备0" in table_chunks[0].content


def test_code_fence_is_atomic():
    code = "```python\n" + "\n".join(f"print({i})" for i in range(30)) + "\n```"
    md = "## 示例\n\n" + code
    chunks = parse_markdown(md, doc_id="code", doc_title="示例", chunk_size=120, overlap=20)
    code_chunks = [c for c in chunks if "print(29)" in c.content]
    assert len(code_chunks) == 1
    assert "print(0)" in code_chunks[0].content


def test_empty_document_returns_no_chunks():
    assert parse_markdown("", doc_id="empty", doc_title="空") == []


def test_table_stays_intact_between_paragraphs():
    rows = ["| 设备 | 数量 |", "| --- | --- |"] + [f"| 设备{i} | {i} |" for i in range(30)]
    table = "\n".join(rows)
    md = "## 清单\n\n" + "这是一段说明文字。" * 5 + "\n\n" + table + "\n\n" + "后续说明。" * 40
    chunks = parse_markdown(md, doc_id="t", doc_title="清单")
    table_chunks = [c for c in chunks if "| 设备0 |" in c.content]
    assert len(table_chunks) == 1
    assert "设备29" in table_chunks[0].content
    assert table_chunks[0].content.lstrip().startswith("|")
    assert sum("设备29" in c.content for c in chunks) == 1


def test_code_fence_stays_intact_between_paragraphs():
    code = "```python\n" + "\n".join(f"print({i})" for i in range(20)) + "\n```"
    md = "## 示例\n\n" + "说明文字。" * 40 + "\n\n" + code + "\n\n" + "结尾说明。" * 40
    chunks = parse_markdown(md, doc_id="c", doc_title="示例")
    code_chunks = [c for c in chunks if "print(19)" in c.content]
    assert len(code_chunks) == 1
    assert code_chunks[0].content.lstrip().startswith("```")
    assert "print(0)" in code_chunks[0].content


def test_chunk_ids_are_stable():
    md = "## 一\n\n内容一。\n\n## 二\n\n内容二。"
    a = parse_markdown(md, doc_id="doc", doc_title="文档")
    b = parse_markdown(md, doc_id="doc", doc_title="文档")
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
