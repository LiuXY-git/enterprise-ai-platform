import pytest

from backend.app.services.llm_config import get_llm_config


def test_get_deepseek_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "deepseek",
    )
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY",
        "deepseek-test-key",
    )
    monkeypatch.setenv(
        "DEEPSEEK_BASE_URL",
        "https://deepseek.example.com",
    )
    monkeypatch.setenv(
        "DEEPSEEK_MODEL",
        "deepseek-test-model",
    )

    config = get_llm_config()

    assert config.provider == "deepseek"
    assert config.api_key == "deepseek-test-key"
    assert config.base_url == "https://deepseek.example.com"
    assert config.model == "deepseek-test-model"


def test_get_qwen_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "qwen",
    )
    monkeypatch.setenv(
        "DASHSCOPE_API_KEY",
        "qwen-test-key",
    )
    monkeypatch.setenv(
        "QWEN_BASE_URL",
        "https://qwen.example.com",
    )
    monkeypatch.setenv(
        "QWEN_MODEL",
        "qwen-test-model",
    )

    config = get_llm_config()

    assert config.provider == "qwen"
    assert config.api_key == "qwen-test-key"
    assert config.base_url == "https://qwen.example.com"
    assert config.model == "qwen-test-model"


def test_get_llm_config_rejects_unknown_provider(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "unknown",
    )

    with pytest.raises(
        RuntimeError,
        match="不支持的 LLM_PROVIDER",
    ):
        get_llm_config()


def test_get_llm_config_requires_active_api_key(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "qwen",
    )
    monkeypatch.delenv(
        "DASHSCOPE_API_KEY",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="未配置 DASHSCOPE_API_KEY",
    ):
        get_llm_config()
