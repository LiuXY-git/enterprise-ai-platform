from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from ..models.external_knowledge import (
    ExternalKnowledgeRecord,
    ExternalKnowledgeRequest,
    ExternalKnowledgeResponse,
)
from ..services.external_knowledge_config import (
    get_external_knowledge_config,
)
from ..services.retrieval_service import search_chunks

router = APIRouter(
    tags=["knowledge"],
)


def distance_to_score(distance: float) -> float:
    normalized_distance = max(
        distance,
        0.0,
    )
    return 1.0 / (1.0 + normalized_distance)


def validate_authorization(
    authorization: str | None,
) -> None:
    try:
        config = get_external_knowledge_config()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()

    if (
        scheme.lower() != "bearer"
        or not token
        or not compare_digest(
            token,
            config.api_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="外部知识库 API Key 无效",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )


@router.post(
    "/retrieval",
    response_model=ExternalKnowledgeResponse,
    summary="为 Dify 检索外部知识",
    description=(
        "按照 Dify 外部知识库协议接收查询，从 Knowledge Hub 中检索相关文档片段。"
    ),
    response_description="符合 Dify 协议的知识片段列表。",
    responses={
        401: {
            "description": "缺少或使用了无效的 Bearer Token。",
        },
        404: {
            "description": "请求的外部知识库不存在。",
        },
        422: {
            "description": "请求参数不符合 Dify 外部知识库协议。",
        },
        503: {
            "description": "外部知识库服务配置不完整。",
        },
    },
)
def retrieve_external_knowledge(
    request: ExternalKnowledgeRequest,
    authorization: Annotated[
        str | None,
        Header(),
    ] = None,
) -> ExternalKnowledgeResponse:
    validate_authorization(
        authorization,
    )

    config = get_external_knowledge_config()

    if request.knowledge_id != config.knowledge_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="外部知识库不存在",
        )

    chunks = search_chunks(
        request.query,
        top_k=request.retrieval_setting.top_k,
    )

    records: list[ExternalKnowledgeRecord] = []

    for chunk in chunks:
        score = distance_to_score(
            chunk.distance,
        )

        if score < request.retrieval_setting.score_threshold:
            continue

        records.append(
            ExternalKnowledgeRecord(
                content=chunk.text,
                score=score,
                title=chunk.source,
                metadata={
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "source": chunk.source,
                    "distance": chunk.distance,
                },
            )
        )

    return ExternalKnowledgeResponse(
        records=records,
    )
