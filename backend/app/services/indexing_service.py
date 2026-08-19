from .chunk_service import split_by_length
from .embedding_service import embed_texts
from .vector_store import get_document_chunks_collection

DEFAULT_CHUNK_SIZE = 200
DEFAULT_OVERLAP = 50


def index_document_text(
    *,
    document_id: str,
    source: str,
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> int:
    chunks = split_by_length(
        text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    if not chunks:
        return 0

    embeddings = embed_texts(chunks)

    record_ids = [f"{document_id}-chunk-{index}" for index in range(len(chunks))]

    metadatas = [
        {
            "document_id": document_id,
            "source": source,
            "chunk_index": index,
            "chunk_size": chunk_size,
            "overlap": overlap,
        }
        for index in range(len(chunks))
    ]

    collection = get_document_chunks_collection()

    collection.upsert(
        ids=record_ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return len(chunks)
