import pytest

from backend.app.services.dify_config import get_dify_workflow_config


def test_get_dify_workflow_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DIFY_WORKFLOW_API_KEY", "test-workflow-key")
    monkeypatch.setenv("DIFY_API_BASE_URL", "http://dify.example/v1/")
    monkeypatch.setenv("DIFY_WORKFLOW_TIMEOUT_SECONDS", "45")

    config = get_dify_workflow_config()

    assert config.api_key == "test-workflow-key"
    assert config.base_url == "http://dify.example/v1"
    assert config.timeout_seconds == 45


def test_get_dify_workflow_config_requires_api_key(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DIFY_WORKFLOW_API_KEY", raising=False)

    with pytest.raises(
        RuntimeError,
        match="未配置 DIFY_WORKFLOW_API_KEY",
    ):
        get_dify_workflow_config()


@pytest.mark.parametrize("value", ["zero", "0", "-1"])
def test_get_dify_workflow_config_validates_timeout(
    monkeypatch,
    value: str,
) -> None:
    monkeypatch.setenv("DIFY_WORKFLOW_API_KEY", "test-workflow-key")
    monkeypatch.setenv("DIFY_WORKFLOW_TIMEOUT_SECONDS", value)

    with pytest.raises(RuntimeError):
        get_dify_workflow_config()
