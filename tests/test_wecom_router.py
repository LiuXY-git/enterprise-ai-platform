import json
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import wecom as wecom_router
from backend.app.services.wecom_config import WeComConfig

URL = "/integrations/wecom/messages"
PAYLOAD = {"text": "Day 45 路由测试", "request_id": "day45-route-001"}


@pytest.fixture
def harness(monkeypatch):
    state = {
        "config": WeComConfig(
            corp_id="ww_test",
            agent_id=1000002,
            app_secret="fake-secret",
            to_user="test_member",
            base_url="https://qyapi.weixin.qq.com",
            timeout_seconds=10,
        ),
        "token_calls": [],
        "send_calls": [],
        "clients": [],
        "send_body": {"errcode": 0, "msgid": "mock-message-id"},
        "send_status": 200,
        "timeout": False,
    }

    def handler(request):
        assert request.url.host == "qyapi.weixin.qq.com"
        if request.url.path == "/cgi-bin/gettoken":
            state["token_calls"].append(request)
            return httpx.Response(
                200,
                json={
                    "access_token": f"fake-token-{len(state['token_calls'])}",
                    "expires_in": 7200,
                },
            )

        assert request.url.path == "/cgi-bin/message/send"
        state["send_calls"].append(request)
        if state["timeout"]:
            raise httpx.ReadTimeout("private-detail fake-secret", request=request)
        return httpx.Response(state["send_status"], json=state["send_body"])

    def create_client():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state["clients"].append(client)
        return client

    monkeypatch.setattr(wecom_router, "get_wecom_config", lambda: state["config"])
    monkeypatch.setattr(wecom_router, "_create_http_client", create_client)

    app = FastAPI()
    app.include_router(wecom_router.router)
    with TestClient(app) as client:
        yield client, app, state

    assert all(client.is_closed for client in state["clients"])


def test_returns_success_and_reuses_token(harness):
    client, app, state = harness
    first = client.post(URL, json=PAYLOAD)
    service = app.state.wecom_cache[1]
    second = client.post(URL, json=PAYLOAD)

    assert first.status_code == second.status_code == 200
    assert first.json() == {
        "status": "sent",
        "message_id": "mock-message-id",
        "request_id": "day45-route-001",
        "attempts": 1,
    }
    assert app.state.wecom_cache[1] is service
    assert len(state["token_calls"]) == 1
    assert len(state["send_calls"]) == 2
    assert all(client.is_closed for client in state["clients"])


def test_config_change_replaces_service_and_token(harness):
    client, app, state = harness
    assert client.post(URL, json=PAYLOAD).status_code == 200
    old_service = app.state.wecom_cache[1]

    state["config"] = replace(
        state["config"], app_secret="new-fake-secret", to_user="another_member"
    )
    assert client.post(URL, json=PAYLOAD).status_code == 200

    assert app.state.wecom_cache[1] is not old_service
    assert len(state["token_calls"]) == 2
    assert state["token_calls"][1].url.params["corpsecret"] == "new-fake-secret"
    assert json.loads(state["send_calls"][1].content)["touser"] == "another_member"


@pytest.mark.parametrize(
    "changes",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "中" * 683},
        {"text": 123},
        {"request_id": "invalid key"},
        {"request_id": "a" * 129},
        {"to_user": "another_member"},
        {"app_secret": "unexpected-secret"},
    ],
)
def test_invalid_input_never_reaches_config_or_network(harness, monkeypatch, changes):
    client, _, state = harness

    def forbidden_config():
        raise AssertionError("Invalid input must not reach the service")

    monkeypatch.setattr(wecom_router, "get_wecom_config", forbidden_config)
    response = client.post(URL, json={**PAYLOAD, **changes})
    assert response.status_code == 422
    assert state["clients"] == []


def test_missing_config_returns_503_but_openapi_works(harness, monkeypatch):
    client, _, state = harness

    def missing_config():
        raise RuntimeError("未配置 WECOM_CORP_ID")

    monkeypatch.setattr(wecom_router, "get_wecom_config", missing_config)
    assert client.get("/openapi.json").status_code == 200
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "wecom_unavailable",
        "message": "未配置 WECOM_CORP_ID",
        "request_id": "day45-route-001",
    }
    assert state["clients"] == []


def test_business_error_returns_safe_503(harness):
    client, _, state = harness
    state["send_body"] = {"errcode": 48002, "errmsg": "private-detail fake-secret"}
    response = client.post(URL, json=PAYLOAD)

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "wecom_unavailable"
    assert "48002" in detail["message"]
    assert "fake-secret" not in response.text
    assert "private-detail" not in response.text
    assert len(state["send_calls"]) == 1


@pytest.mark.parametrize("failure", ["timeout", "bad_json_shape", "gateway"])
def test_unknown_result_is_distinguishable_and_not_retried(harness, failure):
    client, _, state = harness
    if failure == "timeout":
        state["timeout"] = True
    elif failure == "bad_json_shape":
        state["send_body"] = []
    else:
        state["send_status"] = 502

    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "delivery_unknown"
    assert detail["request_id"] == PAYLOAD["request_id"]
    assert "不要自动重发" in detail["message"]
    assert "fake-secret" not in response.text
    assert len(state["send_calls"]) == 1


def test_missing_message_id_is_null(harness):
    client, _, state = harness
    state["send_body"] = {"errcode": 0}
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()["message_id"] is None
