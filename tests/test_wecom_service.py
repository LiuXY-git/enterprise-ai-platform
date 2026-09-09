import asyncio
import json

import httpx
import pytest

from backend.app.models.wecom import WeComTextMessageRequest
from backend.app.services.wecom_config import WeComConfig
from backend.app.services.wecom_service import (
    WeComDeliveryUnknownError,
    WeComMessageService,
)


def build_config():
    return WeComConfig(
        corp_id="ww_test_corp",
        agent_id=1000002,
        app_secret="fake-secret",
        to_user="test_member",
        base_url="https://qyapi.weixin.qq.com",
        timeout_seconds=10,
    )


def build_request():
    return WeComTextMessageRequest(
        text="Day 45 企业微信测试消息",
        request_id="day45-smoke-001",
    )


class FakeWeCom:
    def __init__(self, send_handler, *, token_body=None):
        self.send_handler = send_handler
        self.token_body = token_body
        self.token_calls = []
        self.send_calls = []

    def __call__(self, request):
        assert request.url.host == "qyapi.weixin.qq.com"
        if request.url.path == "/cgi-bin/gettoken":
            assert request.method == "GET"
            self.token_calls.append(request)
            body = self.token_body
            if body is None:
                body = {
                    "errcode": 0,
                    "access_token": f"fake-token-{len(self.token_calls)}",
                    "expires_in": 7200,
                }
            return httpx.Response(200, json=body)

        assert request.url.path == "/cgi-bin/message/send"
        assert request.method == "POST"
        self.send_calls.append(request)
        return self.send_handler(request)


def test_success_payload_and_token_cache(caplog):
    fake = FakeWeCom(
        lambda request: httpx.Response(200, json={"errcode": 0, "msgid": "msg-1"})
    )

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            first = await service.send_text_message(build_request(), client=client)
            second = await service.send_text_message(build_request(), client=client)

        assert first.model_dump() == {
            "status": "sent",
            "message_id": "msg-1",
            "request_id": "day45-smoke-001",
            "attempts": 1,
        }
        assert second.attempts == 1

    with caplog.at_level("INFO", logger="httpx"):
        asyncio.run(scenario())

    assert len(fake.token_calls) == 1
    # Same request_id is NOT a deduplication guarantee.
    assert len(fake.send_calls) == 2
    sent = fake.send_calls[0]
    assert sent.url.params["access_token"] == "fake-token-1"
    assert sent.extensions["timeout"]["read"] == 10
    assert json.loads(sent.content) == {
        "touser": "test_member",
        "msgtype": "text",
        "agentid": 1000002,
        "text": {"content": "Day 45 企业微信测试消息"},
        "safe": 0,
    }
    assert "fake-secret" not in caplog.text
    assert "fake-token-1" not in caplog.text


def test_success_without_message_id():
    fake = FakeWeCom(lambda request: httpx.Response(200, json={"errcode": 0}))

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            result = await service.send_text_message(build_request(), client=client)
        assert result.message_id is None

    asyncio.run(scenario())


@pytest.mark.parametrize("code", [40014, 42001])
def test_refreshes_invalid_token_once(code):
    def handler(request):
        if len(fake.send_calls) == 1:
            return httpx.Response(200, json={"errcode": code})
        return httpx.Response(200, json={"errcode": 0})

    fake = FakeWeCom(handler)

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            result = await service.send_text_message(build_request(), client=client)
        assert result.attempts == 2

    asyncio.run(scenario())
    assert len(fake.token_calls) == 2
    assert len(fake.send_calls) == 2
    assert fake.send_calls[1].url.params["access_token"] == "fake-token-2"


def test_stops_after_second_invalid_token():
    fake = FakeWeCom(lambda request: httpx.Response(200, json={"errcode": 42001}))

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            with pytest.raises(RuntimeError, match="42001"):
                await service.send_text_message(build_request(), client=client)

    asyncio.run(scenario())
    assert len(fake.token_calls) == 2
    assert len(fake.send_calls) == 2


@pytest.mark.parametrize(
    "body,unknown",
    [
        ({"errcode": 48002, "errmsg": "fake-secret private-detail"}, False),
        ({"errcode": 0, "invaliduser": "test_member"}, False),
        ({"errcode": 0, "unlicenseduser": "test_member"}, False),
        ({"errcode": 0, "invaliduser": []}, True),
        ({"errcode": 0, "msgid": ""}, True),
        ({"errcode": 0, "msgid": 123}, True),
        ({"errcode": "0"}, True),
        ({"errcode": False}, True),
        ({}, True),
        ([], True),
    ],
)
def test_rejects_bad_results_without_resending(body, unknown):
    fake = FakeWeCom(lambda request: httpx.Response(200, json=body))

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            with pytest.raises(RuntimeError) as caught:
                await service.send_text_message(build_request(), client=client)
        assert isinstance(caught.value, WeComDeliveryUnknownError) is unknown
        assert "fake-secret" not in str(caught.value)
        assert "private-detail" not in str(caught.value)

    asyncio.run(scenario())
    assert len(fake.send_calls) == 1


@pytest.mark.parametrize("status_code", [302, 400, 408, 429, 500, 502, 503, 504])
def test_http_errors_do_not_retry_or_follow_redirects(status_code):
    fake = FakeWeCom(
        lambda request: httpx.Response(
            status_code,
            headers={"Location": "https://example.com"},
            text="private-detail",
        )
    )

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(fake),
            follow_redirects=True,
        ) as client:
            with pytest.raises(RuntimeError, match=f"HTTP {status_code}") as caught:
                await service.send_text_message(build_request(), client=client)
        unknown = status_code == 408 or status_code >= 500
        assert isinstance(caught.value, WeComDeliveryUnknownError) is unknown
        assert "private-detail" not in str(caught.value)

    asyncio.run(scenario())
    assert len(fake.send_calls) == 1


def test_read_timeout_is_unknown_and_not_retried():
    def handler(request):
        raise httpx.ReadTimeout("private-detail fake-token-1", request=request)

    fake = FakeWeCom(handler)

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            with pytest.raises(WeComDeliveryUnknownError) as caught:
                await service.send_text_message(build_request(), client=client)
        assert "delivery_unknown" in str(caught.value)
        assert "fake-token-1" not in str(caught.value)
        assert caught.value.__suppress_context__ is True

    asyncio.run(scenario())
    assert len(fake.send_calls) == 1


def test_non_json_response_is_unknown():
    fake = FakeWeCom(lambda request: httpx.Response(200, text="not-json"))

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            with pytest.raises(WeComDeliveryUnknownError, match="JSON"):
                await service.send_text_message(build_request(), client=client)

    asyncio.run(scenario())
    assert len(fake.send_calls) == 1


def test_token_failure_prevents_sending():
    def handler(request):
        raise AssertionError("Must not send without a token")

    fake = FakeWeCom(handler, token_body={"errcode": 40013})

    async def scenario():
        service = WeComMessageService(build_config())
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            with pytest.raises(RuntimeError, match="40013"):
                await service.send_text_message(build_request(), client=client)

    asyncio.run(scenario())
    assert len(fake.token_calls) == 1
    assert len(fake.send_calls) == 0
