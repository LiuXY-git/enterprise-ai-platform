from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_DATA_PATH = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "enterprise_documents"


def get_document_collection():
    CHROMA_DATA_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = chromadb.PersistentClient(
        path=str(CHROMA_DATA_PATH),
    )

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=None,
    )
