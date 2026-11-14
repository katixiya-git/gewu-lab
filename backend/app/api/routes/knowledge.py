"""知识库检索接口。"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from redis.exceptions import RedisError

from app.api.deps import get_current_user, get_knowledge_service
from app.core.result import Result
from app.knowledge.embedding import EmbeddingError
from app.knowledge.store import KbStoreError
from app.schemas.knowledge import KnowledgeHitOut, KnowledgeSearchRequest
from app.services.knowledge_service import IndexEmptyError, KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# POST /api/knowledge/search 语义检索
# 需要登录；返回按相似度倒序的片段，附文档名与章节，便于回答里标出处。
# 503 = 索引为空或 AI 未配置；502 = 嵌入服务异常。
@router.post(
    "/search",
    response_model=Result[list[KnowledgeHitOut]],
    summary="知识库语义检索",
    description="把问题向量化后在 Redis HNSW 索引里做 KNN，返回带出处的片段。",
)
async def search_knowledge(
    body: KnowledgeSearchRequest,
    _user=Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> Result[list[KnowledgeHitOut]]:
    """语义检索知识库，返回最相关的若干片段。"""
    try:
        hits = await service.search(body.query, top_k=body.top_k)
    except IndexEmptyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except EmbeddingError as exc:
        logger.warning("%s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="检索服务暂时不可用"
        ) from exc
    except (RedisError, KbStoreError) as exc:
        logger.warning("知识库存储不可用：%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="知识库暂时不可用，请稍后再试"
        ) from exc
    return Result.ok(hits)
