from fastapi import APIRouter

from ..models.rag import (
    RagQueryRequest,
    RagQueryResponse,
    RagSearchResult,
)
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
