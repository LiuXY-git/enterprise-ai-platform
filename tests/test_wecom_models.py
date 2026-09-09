import pytest
from pydantic import ValidationError

from backend.app.models.wecom import (
    WeComMessageResponse,
    WeComTextMessageRequest,
)


def test_request_accepts_valid_input():
    request = WeComTextMessageRequest(
        text="  Day 45 企业微信测试消息  ",
        request_id=" day45-smoke-001 ",
    )

    assert request.text == "Day 45 企业微信测试消息"
    assert request.request_id == "day45-smoke-001"


@pytest.mark.parametrize(
    "text",
    [
        "a" * 2048,
        "中" * 682,
        "😀" * 512,
    ],
)
def test_request_accepts_text_within_byte_limit(text):
    request = WeComTextMessageRequest(
        text=text,
        request_id="day45-boundary",
    )

    assert request.text == text
    assert len(request.text.encode("utf-8")) <= 2048


@pytest.mark.parametrize(
    "text",
    [
        "a" * 2049,
        "中" * 683,
        "😀" * 513,
    ],
)
def test_request_rejects_text_over_byte_limit(text):
    with pytest.raises(ValidationError):
        WeComTextMessageRequest(
            text=text,
            request_id="day45-boundary",
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"text": ""},
        {"text": " \n\t "},
        {"text": None},
        {"text": 123},
        {"text": "\ud800"},
        {"request_id": ""},
        {"request_id": "   "},
        {"request_id": "invalid key"},
        {"request_id": "中文编号"},
        {"request_id": "a" * 129},
        {"request_id": 123},
        {"to_user": "another_member"},
        {"app_secret": "unexpected-secret"},
        {"idempotency_key": "unexpected-key"},
    ],
)
def test_request_rejects_invalid_input(changes):
    payload = {
        "text": "测试消息",
        "request_id": "day45-smoke-001",
        **changes,
    }

    with pytest.raises(ValidationError):
        WeComTextMessageRequest.model_validate(payload)


@pytest.mark.parametrize("missing_field", ["text", "request_id"])
def test_request_requires_fields(missing_field):
    payload = {
        "text": "测试消息",
        "request_id": "day45-smoke-001",
    }
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        WeComTextMessageRequest.model_validate(payload)


def test_request_accepts_max_length_request_id():
    request = WeComTextMessageRequest(
        text="测试消息",
        request_id="a" * 128,
    )

    assert len(request.request_id) == 128


def test_response_accepts_success():
    response = WeComMessageResponse(
        status="sent",
        message_id="test-message-id",
        request_id="day45-smoke-001",
        attempts=1,
    )

    assert response.model_dump() == {
        "status": "sent",
        "message_id": "test-message-id",
        "request_id": "day45-smoke-001",
        "attempts": 1,
    }


def test_response_allows_missing_message_id():
    response = WeComMessageResponse(
        status="sent",
        request_id="day45-smoke-001",
        attempts=1,
    )

    assert response.message_id is None
    assert response.model_dump()["message_id"] is None


def test_response_accepts_second_send_attempt():
    response = WeComMessageResponse(
        status="sent",
        request_id="day45-smoke-001",
        attempts=2,
    )

    assert response.attempts == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"message_id": ""},
        {"message_id": "   "},
        {"request_id": ""},
        {"request_id": "invalid key"},
        {"request_id": "a" * 129},
        {"attempts": 0},
        {"attempts": 3},
        {"attempts": True},
        {"attempts": "1"},
        {"unexpected": "value"},
    ],
)
def test_response_rejects_invalid_result(changes):
    payload = {
        "status": "sent",
        "message_id": "test-message-id",
        "request_id": "day45-smoke-001",
        "attempts": 1,
        **changes,
    }

    with pytest.raises(ValidationError):
        WeComMessageResponse.model_validate(payload)
