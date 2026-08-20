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
