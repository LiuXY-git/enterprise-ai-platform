from dataclasses import dataclass

from .embedding_service import embed_texts
from .vector_store import get_document_chunks_collection

CANDIDATE_MULTIPLIER = 4


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    text: str
    source: str
    chunk_index: int
    distance: float


def search_chunks(
    question: str,
    *,
    top_k: int = 3,
) -> list[RetrievedChunk]:
    normalized_question = question.strip()

    if not normalized_question or top_k <= 0:
        return []

    collection = get_document_chunks_collection()
    record_count = collection.count()

    if record_count == 0:
        return []

    question_embedding = embed_texts(
        [normalized_question],
    )[0]

    candidate_count = min(
        top_k * CANDIDATE_MULTIPLIER,
        record_count,
    )

    query_result = collection.query(
        query_embeddings=[question_embedding],
        n_results=candidate_count,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    ids = query_result["ids"][0] if query_result["ids"] else []
    documents = query_result["documents"][0] if query_result["documents"] else []
    metadatas = query_result["metadatas"][0] if query_result["metadatas"] else []
    distances = query_result["distances"][0] if query_result["distances"] else []

    results: list[RetrievedChunk] = []
    seen_chunks: set[tuple[str, str]] = set()

    for record_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
        strict=True,
    ):
        metadata_values = metadata or {}
        text = document or ""
        source = str(
            metadata_values.get(
                "source",
                "unknown",
            )
        )

        duplicate_key = (
            source,
            text.strip(),
        )

        if duplicate_key in seen_chunks:
            continue

        seen_chunks.add(duplicate_key)

        results.append(
            RetrievedChunk(
                id=record_id,
                text=text,
                source=source,
                chunk_index=int(
                    metadata_values.get(
                        "chunk_index",
                        -1,
                    )
                ),
                distance=(float(distance) if distance is not None else 0.0),
            )
        )

        if len(results) == top_k:
            break

    return results
