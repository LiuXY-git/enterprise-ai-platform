import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import (
    external_knowledge as external_knowledge_router,
)
from backend.app.services.external_knowledge_config import (
    ExternalKnowledgeConfig,
)
from backend.app.services.retrieval_service import RetrievedChunk

app = FastAPI()
app.include_router(
    external_knowledge_router.router,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_external_knowledge_config(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        external_knowledge_router,
        "get_external_knowledge_config",
        lambda: ExternalKnowledgeConfig(
            api_key="test-api-key",
            knowledge_id="enterprise-knowledge-hub",
        ),
    )


def build_payload(
    *,
    knowledge_id: str = "enterprise-knowledge-hub",
    score_threshold: float = 0.0,
) -> dict:
    return {
        "knowledge_id": knowledge_id,
        "query": "当前项目版本是多少？",
        "retrieval_setting": {
            "top_k": 3,
            "score_threshold": score_threshold,
        },
    }


def build_headers(
    api_key: str = "test-api-key",
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
    }


def test_retrieval_returns_dify_records(
    monkeypatch,
) -> None:
    def fake_search_chunks(
        question: str,
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        assert question == "当前项目版本是多少？"
        assert top_k == 3

        return [
            RetrievedChunk(
                id="readme-chunk-13",
                text="当前项目版本为 v1.0.0。",
                source="README.md",
                chunk_index=13,
                distance=0.25,
            )
        ]

    monkeypatch.setattr(
        external_knowledge_router,
        "search_chunks",
        fake_search_chunks,
    )

    response = client.post(
        "/retrieval",
        headers=build_headers(),
        json=build_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["records"]) == 1
    assert body["records"][0]["content"] == "当前项目版本为 v1.0.0。"
    assert body["records"][0]["score"] == pytest.approx(0.8)
    assert body["records"][0]["title"] == "README.md"
    assert body["records"][0]["metadata"]["chunk_index"] == 13


def test_retrieval_filters_records_below_threshold(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        external_knowledge_router,
        "search_chunks",
        lambda question, *, top_k: [
            RetrievedChunk(
                id="readme-chunk-13",
                text="当前项目版本为 v1.0.0。",
                source="README.md",
                chunk_index=13,
                distance=1.0,
            )
        ],
    )

    response = client.post(
        "/retrieval",
        headers=build_headers(),
        json=build_payload(
            score_threshold=0.6,
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "records": [],
    }


def test_retrieval_rejects_invalid_api_key() -> None:
    response = client.post(
        "/retrieval",
        headers=build_headers(
            "invalid-api-key",
        ),
        json=build_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "外部知识库 API Key 无效"


def test_retrieval_rejects_unknown_knowledge_id() -> None:
    response = client.post(
        "/retrieval",
        headers=build_headers(),
        json=build_payload(
            knowledge_id="unknown-knowledge-hub",
        ),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "外部知识库不存在"
