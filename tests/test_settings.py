import importlib
import os
import traceback
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app import settings
from backend.app.services import llm_service


def test_environment_precedence_empty_values_and_literal_secrets(tmp_path, monkeypatch):
    env_file = tmp_path / "config.env"
    env_file.write_text(
        "LLM_PROVIDER=qwen\nDEEPSEEK_API_KEY=file-key\n"
        "DASHSCOPE_API_KEY=${SECRET_TEXT}-literal\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    settings.load_environment(env_file)
    assert os.environ["LLM_PROVIDER"] == "deepseek"
    assert os.environ["DEEPSEEK_API_KEY"] == ""
    assert os.environ["DASHSCOPE_API_KEY"] == "${SECRET_TEXT}-literal"
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        settings.get_llm_config()


def test_default_env_file_does_not_follow_working_directory(tmp_path, monkeypatch):
    project = tmp_path / "project"
    other = tmp_path / "other"
    project.mkdir()
    other.mkdir()
    expected = project / ".env"
    expected.write_text("LLM_PROVIDER=qwen\n", encoding="utf-8")
    (other / ".env").write_text("LLM_PROVIDER=wrong\n", encoding="utf-8")
    monkeypatch.setattr(settings, "DEFAULT_ENV_FILE", expected)
    monkeypatch.chdir(other)
    settings.load_environment()
    assert os.environ["LLM_PROVIDER"] == "qwen"


def test_missing_default_is_optional_but_explicit_file_is_required(tmp_path):
    settings.load_environment()
    with pytest.raises(RuntimeError, match="环境文件"):
        settings.load_environment(tmp_path / "missing.env")


def test_importing_legacy_config_does_not_load_environment(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Import must not load an environment file")

    monkeypatch.setattr(settings, "load_dotenv", forbidden)
    for module in (
        "llm_config",
        "dify_config",
        "external_knowledge_config",
        "feishu_config",
        "feishu_message_config",
        "wecom_config",
    ):
        imported = importlib.import_module(f"backend.app.services.{module}")
        importlib.reload(imported)
    from backend.app.services.llm_config import LLMConfig, get_llm_config

    assert LLMConfig is settings.LLMConfig
    assert get_llm_config is settings.get_llm_config


@pytest.mark.parametrize("provider", ["deepseek", "qwen"])
def test_selected_provider_reaches_mock_model_client(monkeypatch, provider):
    definition = settings.PROVIDER_DEFINITIONS[provider]
    monkeypatch.setenv("LLM_PROVIDER", f" {provider.upper()} ")
    monkeypatch.setenv(definition.api_key_env, "isolated-secret")
    monkeypatch.setenv(definition.base_url_env, f"https://{provider}.example/v1")
    monkeypatch.setenv(definition.model_env, "selected-model")
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="mock answer")),
            ]
        )

    def client(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create),
            )
        )

    monkeypatch.setattr(llm_service, "OpenAI", client)
    assert llm_service.generate_grounded_answer("question", []) == "mock answer"
    assert captured["api_key"] == "isolated-secret"
    assert captured["base_url"] == f"https://{provider}.example/v1"
    assert captured["model"] == "selected-model"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "0", "-1"])
@pytest.mark.parametrize("component", ["dify", "feishu"])
def test_timeout_must_be_finite_positive(monkeypatch, component, value):
    monkeypatch.setenv("DIFY_WORKFLOW_API_KEY", "test-key")
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    name = (
        "DIFY_WORKFLOW_TIMEOUT_SECONDS"
        if component == "dify"
        else "FEISHU_TIMEOUT_SECONDS"
    )
    monkeypatch.setenv(name, value)
    getter = (
        settings.get_dify_workflow_config
        if component == "dify"
        else settings.get_feishu_config
    )
    with pytest.raises(RuntimeError, match=name):
        getter()


@pytest.mark.parametrize(
    "url",
    [
        "https://user:SECRET_MARKER@example.com/v1",
        "https://example.com/v1?key=SECRET_MARKER",
        "https://example.com/v1#SECRET_MARKER",
        "https://[broken",
        "https://example.com:bad",
        "file:///tmp/secret",
        "https://example.com/\nSECRET_MARKER",
        "https://example.com\\SECRET_MARKER",
    ],
)
@pytest.mark.parametrize("component", ["llm", "dify", "feishu"])
def test_invalid_urls_are_rejected_without_reflecting_value(
    monkeypatch, url, component
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DIFY_WORKFLOW_API_KEY", "test-key")
    monkeypatch.setenv("FEISHU_APP_ID", "test-app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    name, getter = {
        "llm": ("DEEPSEEK_BASE_URL", settings.get_llm_config),
        "dify": ("DIFY_API_BASE_URL", settings.get_dify_workflow_config),
        "feishu": ("FEISHU_API_BASE_URL", settings.get_feishu_config),
    }[component]
    monkeypatch.setenv(name, url)
    with pytest.raises(RuntimeError, match=name) as caught:
        getter()
    assert "SECRET_MARKER" not in "".join(traceback.format_exception(caught.value))


def test_unknown_provider_error_does_not_reflect_value(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "SECRET_MARKER")
    with pytest.raises(RuntimeError, match="不支持的 LLM_PROVIDER") as caught:
        settings.get_llm_config()
    assert "SECRET_MARKER" not in str(caught.value)


def test_config_reprs_hide_secrets_and_reads_are_not_cached(monkeypatch):
    values = {
        "DEEPSEEK_API_KEY": "SECRET_MARKER",
        "DIFY_WORKFLOW_API_KEY": "SECRET_MARKER",
        "DIFY_EXTERNAL_KNOWLEDGE_API_KEY": "EXTERNAL_SECRET_MARKER",
        "FEISHU_APP_ID": "app-id",
        "FEISHU_APP_SECRET": "SECRET_MARKER",
        "WECOM_CORP_ID": "corp",
        "WECOM_AGENT_ID": "1",
        "WECOM_APP_SECRET": "SECRET_MARKER",
        "WECOM_TO_USER": "member",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    getters = [
        settings.get_llm_config,
        settings.get_dify_workflow_config,
        settings.get_external_knowledge_config,
        settings.get_feishu_config,
        settings.get_wecom_config,
    ]
    for getter in getters:
        assert "SECRET_MARKER" not in repr(getter())
    assert (
        settings.get_external_knowledge_config().api_key
        != settings.get_dify_workflow_config().api_key
    )
    before = settings.get_wecom_config()
    monkeypatch.setenv("WECOM_APP_SECRET", "new-secret")
    assert settings.get_wecom_config() != before


def test_app_boots_without_optional_integrations(monkeypatch):
    from backend.app import main as main_module
    from backend.app.core import lifecycle as lifecycle_module

    monkeypatch.setattr(lifecycle_module, "init_database", lambda: None)
    monkeypatch.setattr(lifecycle_module, "configure_logging", lambda: None)
    with TestClient(main_module.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        response = client.post(
            "/integrations/wecom/messages",
            json={
                "text": "test",
                "request_id": "day52-test",
            },
        )
        assert response.status_code == 503
        assert "WECOM_CORP_ID" in response.text
