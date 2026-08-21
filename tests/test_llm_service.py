from types import SimpleNamespace

from backend.app.services import llm_service
from backend.app.services.llm_config import LLMConfig
from backend.app.services.retrieval_service import RetrievedChunk


def test_generate_grounded_answer_uses_qwen_config(
    monkeypatch,
) -> None:
    captured: dict = {}

    config = LLMConfig(
        provider="qwen",
        api_key="qwen-test-key",
        base_url="https://qwen.example.com",
        model="qwen3.7-plus",
    )

    def fake_get_llm_config() -> LLMConfig:
        return config

    def fake_create(**kwargs):
        captured["model"] = kwargs["model"]
        captured["messages"] = kwargs["messages"]

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=("项目支持 PDF、DOCX 和 Markdown。[来源1]")
                    )
                )
            ]
        )

    def fake_openai(
        *,
        api_key: str,
        base_url: str,
    ):
        captured["api_key"] = api_key
        captured["base_url"] = base_url

        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=fake_create,
                )
            )
        )

    monkeypatch.setattr(
        llm_service,
        "get_llm_config",
        fake_get_llm_config,
    )
    monkeypatch.setattr(
        llm_service,
        "OpenAI",
        fake_openai,
    )

    chunk = RetrievedChunk(
        id="readme-chunk-0",
        text="项目支持 PDF、DOCX 和 Markdown。",
        source="README.md",
        chunk_index=0,
        distance=0.1,
    )

    answer = llm_service.generate_grounded_answer(
        "项目支持哪些文档格式？",
        [chunk],
    )

    assert captured["api_key"] == "qwen-test-key"
    assert captured["base_url"] == "https://qwen.example.com"
    assert captured["model"] == "qwen3.7-plus"

    messages = captured["messages"]

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "README.md" in messages[1]["content"]
    assert answer.endswith("[来源1]")
