import pytest
from pydantic import ValidationError

from backend.app.models.feishu import (
    FeishuMessageResponse,
    FeishuTextMessageRequest,
)


def test_message_request_accepts_valid_input() -> None:
    request = FeishuTextMessageRequest(
        text="  Day 44 测试消息  ",
        idempotency_key="day44-smoke-001",
    )

    assert request.text == "Day 44 测试消息"
    assert request.idempotency_key == "day44-smoke-001"


@pytest.mark.parametrize(
    "changes",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "a" * 4001},
        {"idempotency_key": ""},
        {"idempotency_key": "invalid key"},
        {"idempotency_key": "a" * 129},
        {"receive_id": "oc_unexpected"},
    ],
)
def test_message_request_rejects_invalid_input(
    changes: dict[str, str],
) -> None:
    payload = {
        "text": "测试消息",
        "idempotency_key": "day44-smoke-001",
        **changes,
    }

    with pytest.raises(ValidationError):
        FeishuTextMessageRequest.model_validate(payload)


def test_message_response_accepts_success() -> None:
    response = FeishuMessageResponse(
        status="sent",
        message_id="om_test",
        attempts=1,
    )

    assert response.model_dump() == {
        "status": "sent",
        "message_id": "om_test",
        "attempts": 1,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"message_id": ""},
        {"attempts": 0},
        {"attempts": 6},
    ],
)
def test_message_response_rejects_invalid_result(
    changes: dict[str, object],
) -> None:
    payload = {
        "status": "sent",
        "message_id": "om_test",
        "attempts": 1,
        **changes,
    }

    with pytest.raises(ValidationError):
        FeishuMessageResponse.model_validate(payload)
