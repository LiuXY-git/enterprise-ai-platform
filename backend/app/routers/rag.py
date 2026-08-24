from fastapi import APIRouter, HTTPException, status

from ..models.rag import (
    RagAnswerResponse,
    RagQueryRequest,
    RagQueryResponse,
    RagSearchResult,
    RagSource,
)
from ..services.rag_service import answer_question
from ..services.retrieval_service import search_chunks

router = APIRouter(
    prefix="/rag",
    tags=["rag"],
)


@router.post(
    "/query",
    response_model=RagQueryResponse,
    summary="检索相关文档片段",
    description=(
        "将用户问题转换为向量，并从 Chroma 向量数据库中检索最相关的"
        "文档片段。该接口只执行检索，不调用大语言模型生成回答。"
    ),
    response_description="按照相关性排序的文档片段列表。",
    responses={
        422: {
            "description": "问题为空，或者 top_k 不在 1 到 10 之间。",
        },
        500: {
            "description": "向量模型或向量数据库处理失败。",
        },
    },
)
def query_rag(
    request: RagQueryRequest,
) -> RagQueryResponse:
    retrieved_chunks = search_chunks(
        request.question,
        top_k=request.top_k,
    )

    results = [
        RagSearchResult(
            id=chunk.id,
            text=chunk.text,
            source=chunk.source,
            chunk_index=chunk.chunk_index,
            distance=chunk.distance,
        )
        for chunk in retrieved_chunks
    ]

    return RagQueryResponse(
        question=request.question,
        results=results,
    )


@router.post(
    "/answer",
    response_model=RagAnswerResponse,
    summary="生成带来源引用的 RAG 回答",
    description=(
        "先从知识库检索相关文档片段，再调用当前配置的大语言模型生成回答。"
        "回答中的 `[来源N]` 标签可以与响应中的 sources 列表对应。"
    ),
    response_description="自然语言回答及其引用来源列表。",
    responses={
        422: {
            "description": "问题为空，或者 top_k 不在 1 到 10 之间。",
        },
        503: {
            "description": "大语言模型配置错误或服务暂时不可用。",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "LLM 调用失败",
                    },
                },
            },
        },
    },
)
def answer_rag(
    request: RagQueryRequest,
) -> RagAnswerResponse:
    try:
        result = answer_question(
            request.question,
            top_k=request.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    sources = [
        RagSource(
            label=f"[来源{index}]",
            id=chunk.id,
            source=chunk.source,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            distance=chunk.distance,
        )
        for index, chunk in enumerate(
            result.chunks,
            start=1,
        )
    ]

    return RagAnswerResponse(
        question=request.question,
        answer=result.answer,
        sources=sources,
    )
