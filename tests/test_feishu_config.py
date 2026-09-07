import pytest

from backend.app.services.feishu_config import get_feishu_config


def test_get_feishu_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    monkeypatch.setenv(
        "FEISHU_API_BASE_URL",
        "https://open.feishu.cn/open-apis/",
    )
    monkeypatch.setenv("FEISHU_TIMEOUT_SECONDS", "15")

    config = get_feishu_config()

    assert config.app_id == "cli_test"
    assert config.app_secret == "test-secret"
    assert config.base_url == "https://open.feishu.cn/open-apis"
    assert config.timeout_seconds == 15


def test_get_feishu_config_requires_app_id(
    monkeypatch,
) -> None:
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")

    with pytest.raises(
        RuntimeError,
        match="未配置 FEISHU_APP_ID",
    ):
        get_feishu_config()


def test_get_feishu_config_requires_app_secret(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)

    with pytest.raises(
        RuntimeError,
        match="未配置 FEISHU_APP_SECRET",
    ):
        get_feishu_config()


def test_get_feishu_config_requires_base_url(
    monkeypatch,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    monkeypatch.setenv("FEISHU_API_BASE_URL", "")

    with pytest.raises(
        RuntimeError,
        match="未配置 FEISHU_API_BASE_URL",
    ):
        get_feishu_config()


@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        "0",
        "-1",
    ],
)
def test_get_feishu_config_validates_timeout(
    monkeypatch,
    value: str,
) -> None:
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test-secret")
    monkeypatch.setenv("FEISHU_TIMEOUT_SECONDS", value)

    with pytest.raises(RuntimeError):
        get_feishu_config()
