from pathlib import Path

from backend.app.services.indexing_service import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
    index_document_text,
)
from backend.app.services.vector_store import (
    DOCUMENT_CHUNKS_COLLECTION_NAME,
    get_document_chunks_collection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = PROJECT_ROOT / "docs" / "week-2.md"
DOCUMENT_ID = "week-2-summary"


def main() -> None:
    text = SOURCE_FILE.read_text(
        encoding="utf-8",
    )

    chunk_count = index_document_text(
        document_id=DOCUMENT_ID,
        source=SOURCE_FILE.name,
        text=text,
    )

    collection = get_document_chunks_collection()

    record_ids = [f"{DOCUMENT_ID}-chunk-{index}" for index in range(chunk_count)]

    result = collection.get(
        ids=record_ids,
        include=[
            "documents",
            "metadatas",
            "embeddings",
        ],
    )

    documents = result["documents"] or []
    metadatas = result["metadatas"] or []
    embeddings = result["embeddings"]

    first_document = documents[0] if documents else ""

    first_metadata = metadatas[0] if metadatas else {}

    first_embedding = embeddings[0] if embeddings is not None else []

    embedding_preview = [round(float(value), 4) for value in first_embedding[:8]]

    print("源文件：", SOURCE_FILE.name)
    print("Collection：", DOCUMENT_CHUNKS_COLLECTION_NAME)
    print("chunk_size：", DEFAULT_CHUNK_SIZE)
    print("overlap：", DEFAULT_OVERLAP)
    print("本次 Chunk 数量：", chunk_count)
    print("Collection 总记录数：", collection.count())
    print("向量维度：", len(first_embedding))
    print()
    print("第一个 Chunk：", first_document)
    print("第一个 Chunk 元数据：", first_metadata)
    print("向量前 8 个数字：", embedding_preview)


if __name__ == "__main__":
    main()
