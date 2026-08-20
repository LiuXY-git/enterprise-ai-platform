import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import rag as rag_router
from backend.app.services.rag_service import GroundedAnswer
from backend.app.services.retrieval_service import RetrievedChunk

app = FastAPI()
app.include_router(rag_router.router)

client = TestClient(app)


def build_test_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        id="readme-chunk-0",
        text="项目支持 PDF、DOCX 和 Markdown。",
        source="README.md",
        chunk_index=0,
        distance=0.1,
    )


def test_query_rag_returns_retrieved_chunks(
    monkeypatch,
) -> None:
    chunk = build_test_chunk()

    def fake_search_chunks(
        question: str,
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        assert top_k == 3
        return [chunk]

    monkeypatch.setattr(
        rag_router,
        "search_chunks",
        fake_search_chunks,
    )

    response = client.post(
        "/rag/query",
        json={
            "question": "项目支持哪些文档格式？",
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["question"] == "项目支持哪些文档格式？"
    assert len(body["results"]) == 1
    assert body["results"][0]["source"] == "README.md"
    assert body["results"][0]["chunk_index"] == 0


def test_answer_rag_returns_answer_and_sources(
    monkeypatch,
) -> None:
    chunk = build_test_chunk()

    def fake_answer_question(
        question: str,
        *,
        top_k: int,
    ) -> GroundedAnswer:
        return GroundedAnswer(
            answer="项目支持 PDF、DOCX 和 Markdown。[来源1]",
            chunks=[chunk],
        )

    monkeypatch.setattr(
        rag_router,
        "answer_question",
        fake_answer_question,
    )

    response = client.post(
        "/rag/answer",
        json={
            "question": "项目支持哪些文档格式？",
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["answer"].endswith("[来源1]")
    assert len(body["sources"]) == 1
    assert body["sources"][0]["label"] == "[来源1]"
    assert body["sources"][0]["source"] == "README.md"


def test_answer_rag_returns_503_when_llm_fails(
    monkeypatch,
) -> None:
    def fake_answer_question(
        question: str,
        *,
        top_k: int,
    ) -> GroundedAnswer:
        raise RuntimeError("LLM 调用失败")

    monkeypatch.setattr(
        rag_router,
        "answer_question",
        fake_answer_question,
    )

    response = client.post(
        "/rag/answer",
        json={
            "question": "项目支持哪些文档格式？",
            "top_k": 3,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "LLM 调用失败"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "question": "",
            "top_k": 3,
        },
        {
            "question": "测试问题",
            "top_k": 0,
        },
        {
            "question": "测试问题",
            "top_k": 11,
        },
    ],
)
def test_rag_request_validation(payload: dict) -> None:
    response = client.post(
        "/rag/query",
        json=payload,
    )

    assert response.status_code == 422
