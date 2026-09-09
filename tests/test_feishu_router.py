import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import feishu as feishu_router
from backend.app.services.feishu_service import FeishuMessageResult

app = FastAPI()
app.include_router(feishu_router.router)
client = TestClient(app)

URL = "/integrations/feishu/messages"


def test_feishu_route_returns_sent_result(monkeypatch) -> None:
    async def fake_send(text: str, *, idempotency_key: str):
        assert text == "Day 44 测试消息"
        assert idempotency_key == "day44-route-001"
        return FeishuMessageResult(
            message_id="om_test",
            attempts=2,
        )

    monkeypatch.setattr(
        feishu_router,
        "send_feishu_text_message",
        fake_send,
    )

    response = client.post(
        URL,
        json={
            "text": "Day 44 测试消息",
            "idempotency_key": "day44-route-001",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "sent",
        "message_id": "om_test",
        "attempts": 2,
    }


@pytest.mark.parametrize(
    "error",
    [
        "无法连接飞书消息服务",
        "飞书消息发送失败（HTTP 403）",
    ],
)
def test_feishu_route_maps_service_error(
    monkeypatch,
    error: str,
) -> None:
    async def fake_send(text: str, *, idempotency_key: str):
        raise RuntimeError(error)

    monkeypatch.setattr(
        feishu_router,
        "send_feishu_text_message",
        fake_send,
    )

    response = client.post(
        URL,
        json={
            "text": "测试消息",
            "idempotency_key": "day44-error-001",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": error}


@pytest.mark.parametrize(
    "changes",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "a" * 4001},
        {"idempotency_key": "invalid key"},
        {"receive_id": "oc_unexpected"},
    ],
)
def test_feishu_route_rejects_invalid_request(
    monkeypatch,
    changes,
) -> None:
    async def forbidden_send(text: str, *, idempotency_key: str):
        raise AssertionError("无效请求不应进入发送服务")

    monkeypatch.setattr(
        feishu_router,
        "send_feishu_text_message",
        forbidden_send,
    )

    response = client.post(
        URL,
        json={
            "text": "测试消息",
            "idempotency_key": "day44-invalid-001",
            **changes,
        },
    )

    assert response.status_code == 422
