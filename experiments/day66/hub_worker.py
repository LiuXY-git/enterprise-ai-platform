"""Reuse Knowledge Hub search in an isolated process; JSON in, JSON out."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from knowledge_tool import DATA, Chunk, KnowledgeError, SearchArguments, parse_json

ROOT = Path(__file__).resolve().parents[2]


def search_hub(request, backend, empty_demo=False):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    from backend.app.services import embedding_service, retrieval_service, vector_store

    # Require an existing cache rather than silently downloading an embedding model.
    cache = ONNXMiniLM_L6_V2.DOWNLOAD_PATH / ONNXMiniLM_L6_V2.EXTRACTED_FOLDER_NAME
    required = [
        "config.json",
        "model.onnx",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "tokenizer.json",
        "vocab.txt",
    ]
    if not all((cache / name).is_file() for name in required):
        raise KnowledgeError("embedding_cache_missing")
    settings = Settings(anonymized_telemetry=False)
    if backend == "hub-demo":
        client = chromadb.EphemeralClient(settings=settings)
        collection = client.create_collection(
            "day66_demo_chunks", embedding_function=None
        )
        records = (
            []
            if empty_demo
            else json.loads(DATA.read_text(encoding="utf-8"))["documents"]
        )
        if records:
            collection.add(
                ids=[r["id"] for r in records],
                documents=[r["text"] for r in records],
                embeddings=embedding_service.embed_texts([r["text"] for r in records]),
                metadatas=[
                    {"source": r["source"], "chunk_index": r["chunk_index"]}
                    for r in records
                ],
            )
    else:
        if not (vector_store.CHROMA_DATA_PATH / "chroma.sqlite3").is_file():
            raise KnowledgeError("knowledge_store_missing")
        client = chromadb.PersistentClient(
            path=str(vector_store.CHROMA_DATA_PATH), settings=settings
        )
        try:
            collection = client.get_collection(
                vector_store.DOCUMENT_CHUNKS_COLLECTION_NAME, embedding_function=None
            )
        except chromadb.errors.NotFoundError:
            raise KnowledgeError("knowledge_collection_missing") from None
    original = retrieval_service.get_document_chunks_collection
    try:
        # Only this dedicated child is rebound, never the running API process.
        retrieval_service.get_document_chunks_collection = lambda: collection
        chunks = retrieval_service.search_chunks(request.query, top_k=request.top_k)
    finally:
        retrieval_service.get_document_chunks_collection = original
    return [Chunk.model_validate(asdict(row)).model_dump() for row in chunks]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["hub-demo", "hub"], required=True)
    parser.add_argument("--empty-demo", action="store_true")
    args = parser.parse_args()
    if args.empty_demo and args.backend != "hub-demo":
        parser.error("--empty-demo requires hub-demo")
    try:
        raw = sys.stdin.read(4097)
        if len(raw) > 4096:
            raise ValueError
        request = SearchArguments.model_validate(parse_json(raw))
        chunks = search_hub(request, args.backend, args.empty_demo)
        print(json.dumps({"status": "ok", "chunks": chunks}, ensure_ascii=False))
        return 0
    except KnowledgeError as exc:
        result = {"status": "error", "error": exc.code}
    except Exception:
        result = {"status": "error", "error": "retrieval_failed"}
    print(json.dumps(result))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
