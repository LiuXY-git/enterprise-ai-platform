from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import crm as crm_router
from backend.app.services.crm_service import (
    CRMConflictError,
    CRMFollowupCreateResult,
    CRMNotFoundError,
    CRMNotificationAttemptResult,
)

CUSTOMER_URL = "/crm/customers/customer-demo-001"
FOLLOWUP_URL = "/crm/followups"


def make_customer_record(**overrides) -> dict:
    timestamp = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)
    record = {
        "customer_id": "customer-demo-001",
        "company_name": "示例制造企业",
        "industry": "制造业",
        "sales_owner": "sales-demo",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    record.update(overrides)
    return record


def make_followup_record(**overrides) -> dict:
    timestamp = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)
    record = {
        "followup_id": "followup-demo-001",
        "customer_id": "customer-demo-001",
        "run_id": "run-demo-001",
        "event_id": "sales-demo-001",
        "requirement_snapshot": "希望建设内部知识库",
        "analysis": {
            "summary": "客户计划评估内部知识库方案。",
            "needs": ["确认文档接入方式"],
            "missing_information": ["文档类型和数量"],
            "next_actions": ["确认文档类型和数量"],
            "risk_flags": [],
        },
        "priority": "high",
        "review_status": "not_required",
        "review_reasons": [],
        "notification_mode": "preview",
        "notification_channel": "feishu",
        "notification_status": "preview",
        "notification_request_key": "sales-followup:run-demo-001",
        "notification_message_id": None,
        "notification_error_code": None,
        "notification_attempt_count": 0,
        "notification_last_attempt_at": None,
        "notification_resolved_at": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    record.update(overrides)
    return record


def make_customer_payload(**overrides) -> dict:
    payload = {
        "customer_id": "customer-demo-001",
        "company_name": "示例制造企业",
        "industry": "制造业",
        "sales_owner": "sales-demo",
    }
    payload.update(overrides)
    return payload


def make_followup_payload(**overrides) -> dict:
    payload = {
        "customer": make_customer_payload(),
        "run_id": "run-demo-001",
        "event_id": "sales-demo-001",
        "requirement_snapshot": "希望建设内部知识库",
        "analysis": {
            "summary": "客户计划评估内部知识库方案。",
            "needs": ["确认文档接入方式"],
            "missing_information": ["文档类型和数量"],
            "next_actions": ["确认文档类型和数量"],
            "risk_flags": [],
        },
        "priority": "high",
        "review_status": "not_required",
        "review_reasons": [],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(crm_router.router)
    return TestClient(app)


def test_put_customer_returns_upserted_record(client, monkeypatch) -> None:
    calls = []

    def fake_upsert(request):
        calls.append(request)
        return make_customer_record()

    monkeypatch.setattr(crm_router, "upsert_customer", fake_upsert)
    response = client.put(CUSTOMER_URL, json=make_customer_payload())

    assert response.status_code == 200
    assert response.json()["customer_id"] == "customer-demo-001"
    assert calls[0].company_name == "示例制造企业"


def test_put_customer_rejects_path_body_mismatch(client, monkeypatch) -> None:
    def forbidden_upsert(request):
        raise AssertionError("不应调用服务层")

    monkeypatch.setattr(crm_router, "upsert_customer", forbidden_upsert)
    response = client.put(
        CUSTOMER_URL,
        json=make_customer_payload(customer_id="customer-demo-002"),
    )

    assert response.status_code == 409
    assert "customer_id" in response.json()["detail"]


def test_get_customer_returns_404(client, monkeypatch) -> None:
    def missing_customer(customer_id):
        raise CRMNotFoundError("找不到指定客户")

    monkeypatch.setattr(crm_router, "get_customer", missing_customer)
    response = client.get(CUSTOMER_URL)

    assert response.status_code == 404
    assert response.json()["detail"] == "找不到指定客户"


@pytest.mark.parametrize(
    "created",
    [True, False],
)
def test_post_followup_exposes_idempotent_creation_result(
    client,
    monkeypatch,
    created,
) -> None:
    monkeypatch.setattr(
        crm_router,
        "create_followup",
        lambda request: CRMFollowupCreateResult(
            record=make_followup_record(),
            created=created,
        ),
    )

    response = client.post(FOLLOWUP_URL, json=make_followup_payload())

    assert response.status_code == 200
    assert response.json()["created"] is created
    assert response.json()["followup_id"] == "followup-demo-001"
    assert response.json()["notification_status"] == "preview"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (CRMNotFoundError("找不到对应的工作流运行"), 404),
        (CRMConflictError("工作流运行与请求不匹配"), 409),
    ],
)
def test_post_followup_maps_service_errors(
    client,
    monkeypatch,
    error,
    expected_status,
) -> None:
    def fail_create(request):
        raise error

    monkeypatch.setattr(crm_router, "create_followup", fail_create)
    response = client.post(FOLLOWUP_URL, json=make_followup_payload())

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)


def test_get_followup_returns_record(client, monkeypatch) -> None:
    monkeypatch.setattr(
        crm_router,
        "get_followup",
        lambda followup_id: make_followup_record(followup_id=followup_id),
    )

    response = client.get("/crm/followups/followup-demo-001")

    assert response.status_code == 200
    assert response.json()["followup_id"] == "followup-demo-001"


def test_list_customer_followups_returns_count(client, monkeypatch) -> None:
    monkeypatch.setattr(
        crm_router,
        "list_customer_followups",
        lambda customer_id: [
            make_followup_record(),
            make_followup_record(
                followup_id="followup-demo-002",
                run_id="run-demo-002",
                event_id="sales-demo-002",
                notification_request_key="sales-followup:run-demo-002",
            ),
        ],
    )

    response = client.get("/crm/customers/customer-demo-001/followups")

    assert response.status_code == 200
    assert response.json()["customer_id"] == "customer-demo-001"
    assert response.json()["count"] == 2
    assert len(response.json()["followups"]) == 2


def test_list_customer_followups_returns_404(client, monkeypatch) -> None:
    def missing_customer(customer_id):
        raise CRMNotFoundError("找不到指定客户")

    monkeypatch.setattr(
        crm_router,
        "list_customer_followups",
        missing_customer,
    )
    response = client.get("/crm/customers/customer-missing/followups")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("url", "method", "payload"),
    [
        (
            "/crm/customers/invalid%20id",
            "get",
            None,
        ),
        (
            CUSTOMER_URL,
            "put",
            make_customer_payload(notification_recipient="@all"),
        ),
        (
            FOLLOWUP_URL,
            "post",
            make_followup_payload(notification_status="sent"),
        ),
    ],
)
def test_invalid_requests_return_422_without_calling_service(
    client,
    monkeypatch,
    url,
    method,
    payload,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("非法请求不应调用服务层")

    monkeypatch.setattr(crm_router, "get_customer", forbidden)
    monkeypatch.setattr(crm_router, "upsert_customer", forbidden)
    monkeypatch.setattr(crm_router, "create_followup", forbidden)

    response = client.request(method, url, json=payload)

    assert response.status_code == 422


def test_notification_attempt_route_returns_stable_request_key(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        crm_router,
        "begin_notification_attempt",
        lambda followup_id, manual: CRMNotificationAttemptResult(
            followup_id=followup_id,
            notification_channel="feishu",
            notification_request_key="sales-followup:run-demo-001",
            attempt_number=1,
            manual=manual,
        ),
    )

    response = client.post(
        "/crm/followups/followup-demo-001/notification-attempts",
        json={"manual": False},
    )

    assert response.status_code == 200
    assert response.json()["attempt_number"] == 1
    assert response.json()["notification_request_key"] == (
        "sales-followup:run-demo-001"
    )


def test_notification_result_route_maps_conflict(
    client,
    monkeypatch,
) -> None:
    def fail_update(*args, **kwargs):
        raise CRMConflictError("通知结果已经记录且不能覆盖")

    monkeypatch.setattr(crm_router, "update_notification_result", fail_update)
    response = client.patch(
        "/crm/followups/followup-demo-001/notification",
        json={"status": "failed", "error_code": "provider_rejected"},
    )

    assert response.status_code == 409
    assert "不能覆盖" in response.json()["detail"]


def test_notification_resolution_route_returns_updated_record(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        crm_router,
        "resolve_unknown_notification",
        lambda followup_id, delivered, message_id: make_followup_record(
            followup_id=followup_id,
            notification_mode="send",
            notification_status="sent" if delivered else "failed",
            notification_message_id=message_id,
            notification_attempt_count=1,
        ),
    )
    response = client.patch(
        "/crm/followups/followup-demo-001/notification-resolution",
        json={"delivered": True, "message_id": "message-001"},
    )

    assert response.status_code == 200
    assert response.json()["notification_status"] == "sent"
    assert response.json()["notification_message_id"] == "message-001"


def test_read_followup_by_run_route(client, monkeypatch) -> None:
    monkeypatch.setattr(
        crm_router,
        "get_followup_by_run",
        lambda run_id: make_followup_record(run_id=run_id),
    )

    response = client.get("/crm/workflow-runs/run-demo-001/followup")

    assert response.status_code == 200
    assert response.json()["run_id"] == "run-demo-001"
