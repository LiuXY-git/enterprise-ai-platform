"""Verify adapter wiring without opening a real business collection."""

import sys
from pathlib import Path
from types import SimpleNamespace

import chromadb
import pytest
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
from hub_worker import search_hub  # noqa: E402
from knowledge_tool import KnowledgeError, SearchArguments  # noqa: E402

from backend.app.services import (  # noqa: E402
    embedding_service,
    retrieval_service,
    vector_store,
)


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    cache = tmp_path / "onnx"
    cache.mkdir()
    for name in [
        "config.json",
        "model.onnx",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "tokenizer.json",
        "vocab.txt",
    ]:
        (cache / name).write_text("fixture")
    monkeypatch.setattr(ONNXMiniLM_L6_V2, "DOWNLOAD_PATH", tmp_path)
    monkeypatch.setattr(vector_store, "CHROMA_DATA_PATH", tmp_path / "business")
    state = SimpleNamespace(
        created=0, opened=0, added=0, queries=0, embeddings=0, rows=[], cache=cache
    )

    class Collection:
        def count(self):
            return len(state.rows)

        def add(self, *, ids, documents, embeddings, metadatas):
            state.added += 1
            state.rows = list(zip(ids, documents, metadatas, strict=True))

        def query(self, **kwargs):
            state.queries += 1
            return {
                "ids": [[r[0] for r in state.rows]],
                "documents": [[r[1] for r in state.rows]],
                "metadatas": [[r[2] for r in state.rows]],
                "distances": [[0.2] * len(state.rows)],
            }

    class Client:
        def create_collection(self, *args, **kwargs):
            state.created += 1
            return Collection()

        def get_collection(self, *args, **kwargs):
            state.opened += 1
            return Collection()

    def embed(texts):
        state.embeddings += 1
        return [[0.1]] * len(texts)

    monkeypatch.setattr(chromadb, "EphemeralClient", lambda **kwargs: Client())
    monkeypatch.setattr(chromadb, "PersistentClient", lambda **kwargs: Client())
    monkeypatch.setattr(embedding_service, "embed_texts", embed)
    monkeypatch.setattr(retrieval_service, "embed_texts", embed)
    state.request = SearchArguments(query="hotel", top_k=3)
    state.original_getter = retrieval_service.get_document_chunks_collection
    return state


def test_demo_uses_existing_search_and_restores_binding(adapter):
    result = search_hub(adapter.request, "hub-demo")
    assert adapter.created == 1 and adapter.added == 1 and adapter.queries == 1
    assert adapter.embeddings == 2 and len(result) == 2
    assert result[0]["id"] == "demo-travel-0"
    assert retrieval_service.get_document_chunks_collection is adapter.original_getter


def test_empty_demo_does_not_embed_or_query(adapter):
    assert search_hub(adapter.request, "hub-demo", True) == []
    assert (
        adapter.created == 1
        and adapter.added == adapter.embeddings == adapter.queries == 0
    )


def test_missing_cache_does_not_download_or_open_store(adapter):
    (adapter.cache / "model.onnx").unlink()
    with pytest.raises(KnowledgeError, match="embedding_cache_missing"):
        search_hub(adapter.request, "hub-demo")
    assert adapter.created == adapter.opened == adapter.embeddings == 0


def test_missing_business_store_does_not_create_it(adapter):
    with pytest.raises(KnowledgeError, match="knowledge_store_missing"):
        search_hub(adapter.request, "hub")
    assert adapter.created == adapter.opened == 0
    assert not vector_store.CHROMA_DATA_PATH.exists()


def prepare_business_store():
    vector_store.CHROMA_DATA_PATH.mkdir()
    (vector_store.CHROMA_DATA_PATH / "chroma.sqlite3").write_text("fixture marker")


def test_existing_collection_only_gets_and_queries(adapter):
    prepare_business_store()
    adapter.rows = [
        ("old-id", "existing text", {"source": "existing.md", "chunk_index": 0})
    ]
    result = search_hub(adapter.request, "hub")
    assert (
        adapter.opened == adapter.queries == 1 and adapter.created == adapter.added == 0
    )
    assert result[0]["id"] == "old-id"


def test_missing_collection_is_not_created(adapter, monkeypatch):
    prepare_business_store()

    class Missing:
        def get_collection(self, *args, **kwargs):
            raise chromadb.errors.NotFoundError("missing")

    monkeypatch.setattr(chromadb, "PersistentClient", lambda **kwargs: Missing())
    with pytest.raises(KnowledgeError, match="knowledge_collection_missing"):
        search_hub(adapter.request, "hub")
    assert adapter.created == adapter.added == 0


def test_getter_restored_when_core_retrieval_fails(adapter, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(retrieval_service, "search_chunks", fail)
    with pytest.raises(RuntimeError):
        search_hub(adapter.request, "hub-demo")
    assert retrieval_service.get_document_chunks_collection is adapter.original_getter
