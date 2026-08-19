from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_DATA_PATH = PROJECT_ROOT / "data" / "chroma"

COLLECTION_NAME = "enterprise_documents"
DOCUMENT_CHUNKS_COLLECTION_NAME = "enterprise_document_chunks"


def get_chroma_client():
    CHROMA_DATA_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    return chromadb.PersistentClient(
        path=str(CHROMA_DATA_PATH),
    )


def get_document_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )


def get_document_chunks_collection():
    client = get_chroma_client()

    return client.get_or_create_collection(
        name=DOCUMENT_CHUNKS_COLLECTION_NAME,
        embedding_function=None,
    )
