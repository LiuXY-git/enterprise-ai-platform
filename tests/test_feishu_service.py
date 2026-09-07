import httpx
import pytest

from backend.app.services import feishu_service
from backend.app.services.feishu_config import FeishuConfig

TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


class FakeResponse:
    def __init__(
        self,
        body: object,
        *,
        status_code: int = 200,
        invalid_json: bool = False,
    ) -> None:
        self.body = body
        self.status_code = status_code
        self.invalid_json = invalid_json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request(
                "POST",
                TOKEN_URL,
            )
            response = httpx.Response(
                self.status_code,
                request=request,
            )
            raise httpx.HTTPStatusError(
                "Feishu error",
                request=request,
                response=response,
            )

    def json(self) -> object:
        if self.invalid_json:
            raise ValueError("invalid JSON")

        return self.body


class FakeAsyncClient:
    def __init__(
        self,
        *,
        timeout: float,
        response: FakeResponse | None,
        captured: dict,
        request_error: httpx.RequestError | None = None,
    ) -> None:
        self.response = response
        self.captured = captured
        self.request_error = request_error
        self.captured["timeout"] = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        json: dict,
    ) -> FakeResponse:
        self.captured["url"] = url
        self.captured["json"] = json

        if self.request_error is not None:
            raise self.request_error

        if self.response is None:
            raise AssertionError("测试没有配置响应")

        return self.response


def build_config() -> FeishuConfig:
    return FeishuConfig(
        app_id="cli_test",
        app_secret="test-secret",
        base_url="https://open.feishu.cn/open-apis",
        timeout_seconds=15,
    )


def install_fake_client(
    monkeypatch,
    *,
    response: FakeResponse | None,
    captured: dict,
    request_error: httpx.RequestError | None = None,
) -> None:
    monkeypatch.setattr(
        feishu_service,
        "get_feishu_config",
        build_config,
    )
    monkeypatch.setattr(
        feishu_service.httpx,
        "AsyncClient",
        lambda *, timeout: FakeAsyncClient(
            timeout=timeout,
            response=response,
            captured=captured,
            request_error=request_error,
        ),
    )


@pytest.mark.anyio
async def test_get_feishu_tenant_token(
    monkeypatch,
) -> None:
    captured: dict = {}
    response = FakeResponse(
        {
            "code": 0,
            "msg": "ok",
            "tenant_access_token": "test-token",
            "expire": 7200,
        }
    )
    install_fake_client(
        monkeypatch,
        response=response,
        captured=captured,
    )

    result = await feishu_service.get_feishu_tenant_token()

    assert captured["url"] == TOKEN_URL
    assert captured["timeout"] == 15
    assert captured["json"] == {
        "app_id": "cli_test",
        "app_secret": "test-secret",
    }
    assert result.access_token == "test-token"
    assert result.expires_in == 7200


@pytest.mark.anyio
async def test_token_rejects_business_error(
    monkeypatch,
) -> None:
    response = FakeResponse(
        {
            "code": 10003,
            "msg": "invalid app",
        }
    )
    install_fake_client(
        monkeypatch,
        response=response,
        captured={},
    )

    with pytest.raises(
        RuntimeError,
        match=r"飞书鉴权失败（业务错误码 10003）",
    ) as exc_info:
        await feishu_service.get_feishu_tenant_token()

    assert "test-secret" not in str(exc_info.value)
    assert "invalid app" not in str(exc_info.value)


@pytest.mark.anyio
async def test_token_hides_http_error_body(
    monkeypatch,
) -> None:
    response = FakeResponse(
        {
            "message": "sensitive remote detail",
        },
        status_code=401,
    )
    install_fake_client(
        monkeypatch,
        response=response,
        captured={},
    )

    with pytest.raises(
        RuntimeError,
        match=r"飞书鉴权失败（HTTP 401）",
    ) as exc_info:
        await feishu_service.get_feishu_tenant_token()

    error_message = str(exc_info.value)

    assert "test-secret" not in error_message
    assert "sensitive remote detail" not in error_message


@pytest.mark.anyio
async def test_token_rejects_invalid_json(
    monkeypatch,
) -> None:
    response = FakeResponse(
        {},
        invalid_json=True,
    )
    install_fake_client(
        monkeypatch,
        response=response,
        captured={},
    )

    with pytest.raises(
        RuntimeError,
        match="飞书鉴权接口返回了无效 JSON",
    ):
        await feishu_service.get_feishu_tenant_token()


@pytest.mark.anyio
async def test_token_requires_access_token(
    monkeypatch,
) -> None:
    response = FakeResponse(
        {
            "code": 0,
            "msg": "ok",
            "expire": 7200,
        }
    )
    install_fake_client(
        monkeypatch,
        response=response,
        captured={},
    )

    with pytest.raises(
        RuntimeError,
        match="缺少 tenant_access_token",
    ):
        await feishu_service.get_feishu_tenant_token()


@pytest.mark.anyio
async def test_token_handles_connection_error(
    monkeypatch,
) -> None:
    request = httpx.Request(
        "POST",
        TOKEN_URL,
    )
    request_error = httpx.ConnectError(
        "connection failed",
        request=request,
    )
    install_fake_client(
        monkeypatch,
        response=None,
        captured={},
        request_error=request_error,
    )

    with pytest.raises(
        RuntimeError,
        match="无法连接飞书开放平台",
    ):
        await feishu_service.get_feishu_tenant_token()
