from scripts.build_kb import load_docs


def test_load_docs_reads_markdown_sorted(tmp_path):
    (tmp_path / "b.md").write_text("# 乙文档\n\n正文 B\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("# 甲文档\n\n正文 A\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("忽略我", encoding="utf-8")

    docs = load_docs(tmp_path)

    assert [doc_id for doc_id, _, _ in docs] == ["a", "b"]
    assert docs[0][1] == "甲文档"
    assert "正文 A" in docs[0][2]


def test_load_docs_falls_back_to_stem(tmp_path):
    (tmp_path / "no-title.md").write_text("## 只有二级标题\n\n正文\n", encoding="utf-8")

    docs = load_docs(tmp_path)

    assert docs[0][0] == "no-title"
    assert docs[0][1] == "no-title"


def test_load_docs_skips_readme(tmp_path):
    (tmp_path / "README.md").write_text("# 语料说明\n\n这只是一份索引。\n", encoding="utf-8")
    (tmp_path / "faq.md").write_text("# 常见问题\n\n正文\n", encoding="utf-8")

    docs = load_docs(tmp_path)

    assert [doc_id for doc_id, _, _ in docs] == ["faq"]
