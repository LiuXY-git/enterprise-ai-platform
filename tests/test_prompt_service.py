from backend.app.services.prompt_service import (
    SYSTEM_PROMPT,
    build_rag_input,
)
from backend.app.services.retrieval_service import RetrievedChunk


def test_system_prompt_contains_grounding_rules() -> None:
    assert "只能根据提供的知识库内容回答" in SYSTEM_PROMPT
    assert "无法从当前知识库确定" in SYSTEM_PROMPT
    assert "不得编造" in SYSTEM_PROMPT
    assert "[来源1]" in SYSTEM_PROMPT


def test_build_rag_input_contains_question_and_sources() -> None:
    chunks = [
        RetrievedChunk(
            id="readme-chunk-0",
            text="项目支持 PDF、DOCX 和 Markdown。",
            source="README.md",
            chunk_index=0,
            distance=0.12,
        ),
        RetrievedChunk(
            id="database-chunk-1",
            text="SQLite 保存文档元数据。",
            source="docs/database.md",
            chunk_index=1,
            distance=0.23,
        ),
    ]

    rag_input = build_rag_input(
        "项目支持哪些文档格式？",
        chunks,
    )

    assert "[来源1]" in rag_input
    assert "[来源2]" in rag_input
    assert "文件：README.md" in rag_input
    assert "文件：docs/database.md" in rag_input
    assert "Chunk：0" in rag_input
    assert "项目支持哪些文档格式？" in rag_input
    assert "<knowledge_context>" in rag_input
    assert "<question>" in rag_input
