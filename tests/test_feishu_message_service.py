import json

import httpx
import pytest

from backend.app.services import feishu_service
from backend.app.services.feishu_config import FeishuConfig
from backend.app.services.feishu_message_config import (
    FeishuMessageConfig,
)


@pytest.fixture
def mock_feishu(monkeypatch):
    async_client_class = httpx.AsyncClient

    monkeypatch.setattr(
        feishu_service,
        "get_feishu_config",
        lambda: FeishuConfig(
            app_id="cli_test",
            app_secret="test-secret",
            base_url="https://open.feishu.cn/open-apis",
            timeout_seconds=10,
        ),
    )
    monkeypatch.setattr(
        feishu_service,
        "get_feishu_message_config",
        lambda: FeishuMessageConfig(
            receive_id_type="chat_id",
            receive_id="oc_test_chat",
            max_attempts=3,
            retry_base_seconds=0.5,
        ),
    )

    async def fake_get_token():
        return feishu_service.FeishuTenantToken(
            access_token="test-token",
            expires_in=7200,
        )

    monkeypatch.setattr(
        feishu_service,
        "get_feishu_tenant_token",
        fake_get_token,
    )

    def install(handler):
        transport = httpx.MockTransport(handler)

        def create_client(*, timeout):
            return async_client_class(
                timeout=timeout,
                transport=transport,
            )

        monkeypatch.setattr(
            feishu_service.httpx,
            "AsyncClient",
            create_client,
        )

    return install


@pytest.mark.anyio
async def test_send_message_builds_correct_request(
    mock_feishu,
) -> None:
    def handler(request):
        assert request.method == "POST"
        assert request.url.scheme == "https"
        assert request.url.host == "open.feishu.cn"
        assert request.url.path == "/open-apis/im/v1/messages"
        assert request.url.params["receive_id_type"] == "chat_id"
        assert request.headers["Authorization"] == "Bearer test-token"

        payload = json.loads(request.content)

        assert payload["receive_id"] == "oc_test_chat"
        assert payload["msg_type"] == "text"
        assert isinstance(payload["content"], str)
        assert json.loads(payload["content"]) == {
            "text": "测试日报\n成功率 100%",
        }
        assert len(payload["uuid"]) == 36
        assert "app_secret" not in payload

        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"message_id": "om_test"},
            },
        )

    mock_feishu(handler)

    result = await feishu_service.send_feishu_text_message(
        "测试日报\n成功率 100%",
        idempotency_key="day44-test-001",
    )

    assert result.message_id == "om_test"
    assert result.attempts == 1


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 401, 403, 500])
async def test_send_message_handles_http_error(
    mock_feishu,
    status_code: int,
) -> None:
    mock_feishu(
        lambda request: httpx.Response(
            status_code,
            json={"detail": "sensitive remote detail"},
        )
    )

    with pytest.raises(
        RuntimeError,
        match=f"HTTP {status_code}",
    ) as exc_info:
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key="day44-http-error",
        )

    error = str(exc_info.value)

    assert "sensitive remote detail" not in error
    assert "test-secret" not in error
    assert "test-token" not in error


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        (
            {
                "code": 230001,
                "msg": "sensitive remote detail test-secret test-token",
            },
            230001,
        ),
        ({"code": "test-token", "msg": "sensitive remote detail"}, None),
        ({"code": False}, None),
        ({"msg": "sensitive remote detail"}, None),
        (["sensitive remote detail"], None),
    ],
)
async def test_http_error_exposes_only_numeric_business_code(
    mock_feishu,
    retry_waits,
    caplog,
    body: object,
    expected_code: int | None,
) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, json=body)

    mock_feishu(handler)

    with pytest.raises(RuntimeError) as exc_info:
        await feishu_service.send_feishu_text_message(
            "私密日报正文",
            idempotency_key="day44-http-business-code",
        )

    expected_error = "飞书消息发送失败（HTTP 400）"
    if expected_code is not None:
        expected_error += f"（业务错误码 {expected_code}）"

    assert str(exc_info.value) == expected_error
    assert expected_error in caplog.text
    assert len(calls) == 1
    assert retry_waits == []

    for secret in [
        "sensitive remote detail",
        "test-secret",
        "test-token",
        "oc_test_chat",
        "私密日报正文",
    ]:
        assert secret not in str(exc_info.value)
        assert secret not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "error"),
    [
        ([], "返回格式错误"),
        ({}, "缺少有效业务错误码"),
        ({"code": False}, "缺少有效业务错误码"),
        (
            {"code": 999, "msg": "sensitive remote detail"},
            "业务错误码 999",
        ),
        ({"code": 0}, "缺少 data"),
        ({"code": 0, "data": {}}, "缺少 message_id"),
    ],
)
async def test_send_message_rejects_invalid_response(
    mock_feishu,
    body: object,
    error: str,
) -> None:
    mock_feishu(
        lambda request: httpx.Response(
            200,
            json=body,
        )
    )

    with pytest.raises(
        RuntimeError,
        match=error,
    ) as exc_info:
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key="day44-invalid-response",
        )

    assert "sensitive remote detail" not in str(exc_info.value)


@pytest.mark.anyio
async def test_send_message_rejects_invalid_json(
    mock_feishu,
) -> None:
    mock_feishu(
        lambda request: httpx.Response(
            200,
            text="not-json",
        )
    )

    with pytest.raises(RuntimeError, match="无效 JSON"):
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key="day44-invalid-json",
        )


@pytest.mark.anyio
async def test_send_message_handles_connection_error(
    mock_feishu,
) -> None:
    def handler(request):
        raise httpx.ConnectError(
            "connection failed",
            request=request,
        )

    mock_feishu(handler)

    with pytest.raises(
        RuntimeError,
        match="无法连接飞书消息服务",
    ):
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key="day44-network-error",
        )


@pytest.mark.anyio
async def test_message_uuid_is_stable(
    mock_feishu,
) -> None:
    uuids = []

    def handler(request):
        payload = json.loads(request.content)
        uuids.append(payload["uuid"])

        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"message_id": "om_test"},
            },
        )

    mock_feishu(handler)

    for key in ["same-key", "same-key", "new-key"]:
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key=key,
        )

    assert uuids[0] == uuids[1]
    assert uuids[0] != uuids[2]


@pytest.fixture(autouse=True)
def retry_waits(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(feishu_service, "sleep", fake_sleep)
    return waits


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    ["network", 429, 500, 502, 503, 504],
)
async def test_retry_recovers(
    mock_feishu,
    retry_waits,
    failure,
):
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))

        if len(payloads) == 1:
            if failure == "network":
                raise httpx.ConnectError(
                    "temporary failure",
                    request=request,
                )
            return httpx.Response(failure)

        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"message_id": "om_recovered"},
            },
        )

    mock_feishu(handler)

    result = await feishu_service.send_feishu_text_message(
        "测试消息",
        idempotency_key="day44-retry",
    )

    assert result.message_id == "om_recovered"
    assert result.attempts == 2
    assert len(payloads) == 2
    assert payloads[0] == payloads[1]
    assert retry_waits == [0.5]


@pytest.mark.anyio
async def test_retry_stops_at_limit(
    mock_feishu,
    retry_waits,
    caplog,
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            503,
            json={"detail": "sensitive remote detail"},
        )

    mock_feishu(handler)

    with pytest.raises(RuntimeError, match="HTTP 503"):
        await feishu_service.send_feishu_text_message(
            "私密日报正文",
            idempotency_key="day44-exhausted",
        )

    assert len(calls) == 3
    assert retry_waits == [0.5, 1.0]
    assert "attempt=3/3" in caplog.text

    for secret in [
        "test-secret",
        "test-token",
        "oc_test_chat",
        "私密日报正文",
        "sensitive remote detail",
    ]:
        assert secret not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [400, 401, 403])
async def test_permanent_http_error_is_not_retried(
    mock_feishu,
    retry_waits,
    status_code,
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status_code)

    mock_feishu(handler)

    with pytest.raises(
        RuntimeError,
        match=f"HTTP {status_code}",
    ):
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key="day44-no-retry",
        )

    assert len(calls) == 1
    assert retry_waits == []


@pytest.mark.anyio
async def test_retry_respects_server_delay(
    mock_feishu,
    retry_waits,
):
    responses = iter(
        [
            httpx.Response(
                429,
                headers={"Retry-After": "2"},
            ),
            httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"message_id": "om_after_wait"},
                },
            ),
        ]
    )

    mock_feishu(lambda request: next(responses))

    result = await feishu_service.send_feishu_text_message(
        "测试消息",
        idempotency_key="day44-server-delay",
    )

    assert result.attempts == 2
    assert retry_waits == [2]


@pytest.mark.anyio
async def test_retry_rejects_unsupported_delay(
    mock_feishu,
    retry_waits,
):
    mock_feishu(
        lambda request: httpx.Response(
            429,
            headers={"Retry-After": "invalid"},
        )
    )

    with pytest.raises(RuntimeError, match="Retry-After"):
        await feishu_service.send_feishu_text_message(
            "测试消息",
            idempotency_key="day44-unsupported-delay",
        )

    assert retry_waits == []
