from dataclasses import dataclass

from .llm_service import generate_grounded_answer
from .retrieval_service import RetrievedChunk, search_chunks


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    chunks: list[RetrievedChunk]


def answer_question(
    question: str,
    *,
    top_k: int = 3,
) -> GroundedAnswer:
    chunks = search_chunks(
        question,
        top_k=top_k,
    )

    if not chunks:
        return GroundedAnswer(
            answer="无法从当前知识库确定。",
            chunks=[],
        )

    answer = generate_grounded_answer(
        question,
        chunks,
    )

    return GroundedAnswer(
        answer=answer,
        chunks=chunks,
    )
