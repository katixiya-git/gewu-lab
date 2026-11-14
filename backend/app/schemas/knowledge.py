"""知识库检索的请求/响应模型。"""

from pydantic import Field

from app.schemas.common import CamelModel


class KnowledgeSearchRequest(CamelModel):
    """检索入参：问题文本 + 返回条数。"""

    query: str = Field(min_length=1, max_length=500, description="检索问题")
    top_k: int = Field(default=5, ge=1, le=10, alias="topK")


class KnowledgeHitOut(CamelModel):
    """单条检索结果：片段正文 + 出处（文档名/章节）+ 相似度。"""

    doc_id: str
    doc_title: str
    section: str
    content: str
    similarity: float
