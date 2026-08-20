from backend.app.services import rag_service
from backend.app.services.retrieval_service import RetrievedChunk


def build_test_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        id="readme-chunk-0",
        text="项目支持 PDF、DOCX 和 Markdown。",
        source="README.md",
        chunk_index=0,
        distance=0.1,
    )


def test_answer_question_returns_fallback_when_no_chunks(
    monkeypatch,
) -> None:
    def fake_search_chunks(
        question: str,
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        return []

    def fail_if_llm_is_called(
        question: str,
        chunks: list[RetrievedChunk],
    ) -> str:
        raise AssertionError("没有检索结果时不应该调用 LLM")

    monkeypatch.setattr(
        rag_service,
        "search_chunks",
        fake_search_chunks,
    )
    monkeypatch.setattr(
        rag_service,
        "generate_grounded_answer",
        fail_if_llm_is_called,
    )

    result = rag_service.answer_question(
        "知识库中不存在的问题",
        top_k=3,
    )

    assert result.answer == "无法从当前知识库确定。"
    assert result.chunks == []


def test_answer_question_returns_answer_and_chunks(
    monkeypatch,
) -> None:
    chunk = build_test_chunk()

    def fake_search_chunks(
        question: str,
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        assert question == "项目支持哪些文档格式？"
        assert top_k == 3
        return [chunk]

    def fake_generate_grounded_answer(
        question: str,
        chunks: list[RetrievedChunk],
    ) -> str:
        assert chunks == [chunk]
        return "项目支持 PDF、DOCX 和 Markdown。[来源1]"

    monkeypatch.setattr(
        rag_service,
        "search_chunks",
        fake_search_chunks,
    )
    monkeypatch.setattr(
        rag_service,
        "generate_grounded_answer",
        fake_generate_grounded_answer,
    )

    result = rag_service.answer_question(
        "项目支持哪些文档格式？",
        top_k=3,
    )

    assert result.answer == "项目支持 PDF、DOCX 和 Markdown。[来源1]"
    assert result.chunks == [chunk]
