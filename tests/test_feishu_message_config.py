import pytest

from backend.app.services.feishu_message_config import (
    get_feishu_message_config,
)


@pytest.fixture(autouse=True)
def message_environment(monkeypatch) -> None:
    """为每个测试设置独立配置，避免依赖本地 .env。"""
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID_TYPE",
        "chat_id",
    )
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID",
        "oc_test_chat",
    )
    monkeypatch.setenv(
        "FEISHU_MAX_ATTEMPTS",
        "3",
    )
    monkeypatch.setenv(
        "FEISHU_RETRY_BASE_SECONDS",
        "0.5",
    )


@pytest.mark.parametrize(
    ("receive_id_type", "receive_id"),
    [
        ("chat_id", "oc_test_chat"),
        ("open_id", "ou_test_user"),
    ],
)
def test_get_feishu_message_config(
    monkeypatch,
    receive_id_type: str,
    receive_id: str,
) -> None:
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID_TYPE",
        receive_id_type,
    )
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID",
        receive_id,
    )

    config = get_feishu_message_config()

    assert config.receive_id_type == receive_id_type
    assert config.receive_id == receive_id
    assert config.max_attempts == 3
    assert config.retry_base_seconds == 0.5


def test_message_config_uses_defaults(monkeypatch) -> None:
    monkeypatch.delenv(
        "FEISHU_RECEIVE_ID_TYPE",
        raising=False,
    )
    monkeypatch.delenv(
        "FEISHU_MAX_ATTEMPTS",
        raising=False,
    )
    monkeypatch.delenv(
        "FEISHU_RETRY_BASE_SECONDS",
        raising=False,
    )

    config = get_feishu_message_config()

    assert config.receive_id_type == "chat_id"
    assert config.max_attempts == 3
    assert config.retry_base_seconds == 0.5


def test_message_config_requires_receive_id(monkeypatch) -> None:
    monkeypatch.delenv(
        "FEISHU_RECEIVE_ID",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="未配置 FEISHU_RECEIVE_ID",
    ):
        get_feishu_message_config()


@pytest.mark.parametrize(
    ("variable", "value", "error"),
    [
        (
            "FEISHU_RECEIVE_ID_TYPE",
            "email",
            "FEISHU_RECEIVE_ID_TYPE 必须是",
        ),
        (
            "FEISHU_RECEIVE_ID",
            "   ",
            "未配置 FEISHU_RECEIVE_ID",
        ),
        (
            "FEISHU_RECEIVE_ID",
            "ou_wrong_type",
            "FEISHU_RECEIVE_ID 必须是以 oc_",
        ),
        (
            "FEISHU_RECEIVE_ID",
            "oc_",
            "FEISHU_RECEIVE_ID 必须是以 oc_",
        ),
        (
            "FEISHU_MAX_ATTEMPTS",
            "abc",
            "FEISHU_MAX_ATTEMPTS 必须是整数",
        ),
        (
            "FEISHU_MAX_ATTEMPTS",
            "1.5",
            "FEISHU_MAX_ATTEMPTS 必须是整数",
        ),
        (
            "FEISHU_MAX_ATTEMPTS",
            "0",
            "FEISHU_MAX_ATTEMPTS 必须在",
        ),
        (
            "FEISHU_MAX_ATTEMPTS",
            "6",
            "FEISHU_MAX_ATTEMPTS 必须在",
        ),
        (
            "FEISHU_RETRY_BASE_SECONDS",
            "abc",
            "FEISHU_RETRY_BASE_SECONDS 必须是数字",
        ),
        (
            "FEISHU_RETRY_BASE_SECONDS",
            "-0.5",
            "FEISHU_RETRY_BASE_SECONDS 必须是大于等于 0",
        ),
        (
            "FEISHU_RETRY_BASE_SECONDS",
            "nan",
            "FEISHU_RETRY_BASE_SECONDS 必须是大于等于 0",
        ),
        (
            "FEISHU_RETRY_BASE_SECONDS",
            "inf",
            "FEISHU_RETRY_BASE_SECONDS 必须是大于等于 0",
        ),
    ],
)
def test_message_config_rejects_invalid_values(
    monkeypatch,
    variable: str,
    value: str,
    error: str,
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(RuntimeError, match=error):
        get_feishu_message_config()


def test_open_id_rejects_chat_id(monkeypatch) -> None:
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID_TYPE",
        "open_id",
    )

    with pytest.raises(
        RuntimeError,
        match="FEISHU_RECEIVE_ID 必须是以 ou_",
    ):
        get_feishu_message_config()


@pytest.mark.parametrize("max_attempts", [1, 5])
def test_message_config_accepts_boundaries(
    monkeypatch,
    max_attempts: int,
) -> None:
    monkeypatch.setenv(
        "FEISHU_MAX_ATTEMPTS",
        str(max_attempts),
    )
    monkeypatch.setenv(
        "FEISHU_RETRY_BASE_SECONDS",
        "0",
    )

    config = get_feishu_message_config()

    assert config.max_attempts == max_attempts
    assert config.retry_base_seconds == 0


def test_message_config_strips_whitespace(monkeypatch) -> None:
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID_TYPE",
        " chat_id ",
    )
    monkeypatch.setenv(
        "FEISHU_RECEIVE_ID",
        " oc_test_chat ",
    )

    config = get_feishu_message_config()

    assert config.receive_id_type == "chat_id"
    assert config.receive_id == "oc_test_chat"
