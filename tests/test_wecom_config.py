import pytest

from backend.app.services.wecom_config import get_wecom_config


@pytest.fixture(autouse=True)
def wecom_env(monkeypatch):
    # 每个测试都使用假配置，不依赖本地 .env 中的真实凭据。
    monkeypatch.setenv("WECOM_CORP_ID", "ww_test_corp")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000002")
    monkeypatch.setenv("WECOM_APP_SECRET", "fake-secret-for-tests")
    monkeypatch.setenv("WECOM_TO_USER", "test_member")

    # 清除本地环境中的可选配置，确保默认值测试稳定。
    monkeypatch.delenv("WECOM_API_BASE_URL", raising=False)
    monkeypatch.delenv("WECOM_TIMEOUT_SECONDS", raising=False)


def test_get_wecom_config_defaults():
    config = get_wecom_config()

    assert config.corp_id == "ww_test_corp"
    assert config.agent_id == 1000002
    assert isinstance(config.agent_id, int)
    assert config.app_secret == "fake-secret-for-tests"
    assert config.to_user == "test_member"
    assert config.base_url == "https://qyapi.weixin.qq.com"
    assert config.timeout_seconds == 10.0


def test_get_wecom_config_strips_whitespace(monkeypatch):
    monkeypatch.setenv("WECOM_CORP_ID", " ww_test_corp ")
    monkeypatch.setenv("WECOM_AGENT_ID", " 1000002 ")
    monkeypatch.setenv("WECOM_APP_SECRET", " fake-secret-for-tests ")
    monkeypatch.setenv("WECOM_TO_USER", " test_member ")
    monkeypatch.setenv(
        "WECOM_API_BASE_URL",
        " https://qyapi.weixin.qq.com/ ",
    )
    monkeypatch.setenv("WECOM_TIMEOUT_SECONDS", " 15.5 ")

    config = get_wecom_config()

    assert config.corp_id == "ww_test_corp"
    assert config.agent_id == 1000002
    assert config.app_secret == "fake-secret-for-tests"
    assert config.to_user == "test_member"
    assert config.base_url == "https://qyapi.weixin.qq.com"
    assert config.timeout_seconds == 15.5


@pytest.mark.parametrize(
    "name",
    [
        "WECOM_CORP_ID",
        "WECOM_AGENT_ID",
        "WECOM_APP_SECRET",
        "WECOM_TO_USER",
    ],
)
@pytest.mark.parametrize("value", [None, "   "])
def test_required_configuration(monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match=f"未配置 {name}"):
        get_wecom_config()


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "1.5", "abc", "+1000002", "１０００００２"],
)
def test_invalid_agent_id(monkeypatch, value):
    monkeypatch.setenv("WECOM_AGENT_ID", value)

    with pytest.raises(RuntimeError, match="WECOM_AGENT_ID"):
        get_wecom_config()


@pytest.mark.parametrize(
    "value",
    ["", "abc", "0", "-1", "nan", "inf", "-inf"],
)
def test_invalid_timeout(monkeypatch, value):
    monkeypatch.setenv("WECOM_TIMEOUT_SECONDS", value)

    with pytest.raises(RuntimeError, match="WECOM_TIMEOUT_SECONDS"):
        get_wecom_config()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "http://qyapi.weixin.qq.com",
        "https://example.com",
        "https://qyapi.weixin.qq.com.example.com",
    ],
)
def test_invalid_base_url(monkeypatch, value):
    monkeypatch.setenv("WECOM_API_BASE_URL", value)

    with pytest.raises(RuntimeError, match="WECOM_API_BASE_URL"):
        get_wecom_config()


@pytest.mark.parametrize(
    "value",
    ["@all", "member_a|member_b", "member a"],
)
def test_rejects_broadcast_and_invalid_recipient(monkeypatch, value):
    monkeypatch.setenv("WECOM_TO_USER", value)

    with pytest.raises(RuntimeError, match="WECOM_TO_USER"):
        get_wecom_config()


def test_config_repr_hides_secret():
    config = get_wecom_config()

    assert "fake-secret-for-tests" not in repr(config)
