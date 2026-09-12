import json
from datetime import UTC, datetime

import pytest

from backend.app import database
from backend.app.models.crm import (
    CRMCustomerUpsertRequest,
    CRMFollowupCreateRequest,
    CRMFollowupResponse,
)
from backend.app.services import crm_service, workflow_run_service
from backend.app.services.crm_service import CRMConflictError, CRMNotFoundError


def initialize_temp_database(monkeypatch, tmp_path):
    database_path = tmp_path / "crm-service-test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    database.init_database()
    return database_path


def insert_workflow_run(
    *,
    run_id="run-demo-001",
    event_id="sales-demo-001",
    workflow_name="sales-followup-assistant",
    status="running",
) -> None:
    connection = database.get_connection()
    try:
        connection.execute(
            """
            INSERT INTO workflow_runs (
                run_id,
                event_id,
                workflow_name,
                source,
                requester,
                report_date,
                status,
                input_json,
                n8n_execution_id,
                started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event_id,
                workflow_name,
                "manual_demo",
                "sales-demo",
                "2026-09-09",
                status,
                "{}",
                f"execution-{run_id}",
                "2026-09-09T08:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def make_followup(**overrides) -> CRMFollowupCreateRequest:
    payload = {
        "customer": {
            "customer_id": "customer-demo-001",
            "company_name": "示例制造企业",
            "industry": "制造业",
            "sales_owner": "sales-demo",
        },
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
    }
    payload.update(overrides)
    return CRMFollowupCreateRequest.model_validate(payload)


def test_upsert_customer_creates_and_updates_record(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    first_time = "2026-09-09T08:00:00+00:00"
    second_time = "2026-09-09T09:00:00+00:00"
    times = iter([first_time, second_time])
    monkeypatch.setattr(crm_service, "_current_time", lambda: next(times))

    created = crm_service.upsert_customer(
        CRMCustomerUpsertRequest(
            customer_id="customer-demo-001",
            company_name="示例制造企业",
            industry="制造业",
            sales_owner="sales-demo",
        )
    )
    updated = crm_service.upsert_customer(
        CRMCustomerUpsertRequest(
            customer_id="customer-demo-001",
            company_name="示例制造企业更新",
            industry=None,
            sales_owner="sales-owner-002",
        )
    )

    assert created["created_at"] == datetime.fromisoformat(first_time)
    assert updated["created_at"] == datetime.fromisoformat(first_time)
    assert updated["updated_at"] == datetime.fromisoformat(second_time)
    assert updated["company_name"] == "示例制造企业更新"
    assert updated["industry"] is None
    assert updated["sales_owner"] == "sales-owner-002"


def test_create_followup_saves_customer_and_preview_atomically(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()

    result = crm_service.create_followup(make_followup())

    assert result.created is True
    assert result.record["customer_id"] == "customer-demo-001"
    assert result.record["notification_status"] == "preview"
    assert result.record["notification_request_key"] == (
        "sales-followup:run-demo-001"
    )
    assert result.record["analysis"]["summary"] == (
        "客户计划评估内部知识库方案。"
    )
    assert crm_service.get_customer("customer-demo-001")["company_name"] == (
        "示例制造企业"
    )

    validated = CRMFollowupResponse.model_validate(result.record)
    assert validated.followup_id == result.record["followup_id"]


def test_create_followup_rolls_back_customer_when_run_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)

    with pytest.raises(CRMNotFoundError, match="工作流运行"):
        crm_service.create_followup(make_followup())

    with pytest.raises(CRMNotFoundError, match="客户"):
        crm_service.get_customer("customer-demo-001")


@pytest.mark.parametrize(
    "workflow_changes",
    [
        {"event_id": "sales-demo-other"},
        {"workflow_name": "another-workflow"},
        {"status": "succeeded"},
    ],
)
def test_create_followup_rejects_mismatched_workflow_run(
    monkeypatch,
    tmp_path,
    workflow_changes,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run(**workflow_changes)

    with pytest.raises(CRMConflictError):
        crm_service.create_followup(make_followup())

    with pytest.raises(CRMNotFoundError, match="客户"):
        crm_service.get_customer("customer-demo-001")


def test_duplicate_run_returns_original_followup_without_new_write(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    first = crm_service.create_followup(make_followup())

    duplicate = crm_service.create_followup(
        make_followup(
            customer={
                "customer_id": "customer-demo-001",
                "company_name": "不应覆盖原客户",
                "industry": None,
                "sales_owner": "sales-other",
            }
        )
    )

    assert duplicate.created is False
    assert duplicate.record["followup_id"] == first.record["followup_id"]
    assert crm_service.get_customer("customer-demo-001")["company_name"] == (
        "示例制造企业"
    )
    assert len(crm_service.list_customer_followups("customer-demo-001")) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"event_id": "sales-demo-other"},
        {
            "customer": {
                "customer_id": "customer-demo-other",
                "company_name": "其他示例企业",
                "industry": None,
                "sales_owner": "sales-demo",
            }
        },
    ],
)
def test_duplicate_run_rejects_different_business_identity(
    monkeypatch,
    tmp_path,
    changes,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    crm_service.create_followup(make_followup())

    with pytest.raises(CRMConflictError, match="其他客户或业务事件"):
        crm_service.create_followup(make_followup(**changes))


def test_pending_review_skips_notification(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    risk_flags = ["pricing_or_discount"]

    result = crm_service.create_followup(
        make_followup(
            analysis={
                "summary": "客户询问正式报价。",
                "needs": ["获取正式报价"],
                "missing_information": ["采购范围"],
                "next_actions": ["由销售核对报价政策"],
                "risk_flags": risk_flags,
            },
            review_status="pending",
            review_reasons=risk_flags,
            notification_mode="send",
        )
    )

    assert result.record["review_status"] == "pending"
    assert result.record["notification_status"] == "skipped"
    assert result.record["notification_request_key"] is None


def test_send_mode_starts_with_pending_notification(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()

    result = crm_service.create_followup(
        make_followup(notification_mode="send", notification_channel="wecom")
    )

    assert result.record["notification_status"] == "pending"
    assert result.record["notification_channel"] == "wecom"
    assert result.record["notification_request_key"] == (
        "sales-followup:run-demo-001"
    )


def test_list_customer_followups_preserves_order(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    insert_workflow_run(run_id="run-demo-002", event_id="sales-demo-002")
    times = iter(
        [
            "2026-09-09T08:00:00+00:00",
            "2026-09-09T09:00:00+00:00",
        ]
    )
    monkeypatch.setattr(crm_service, "_current_time", lambda: next(times))

    first = crm_service.create_followup(make_followup())
    second = crm_service.create_followup(
        make_followup(run_id="run-demo-002", event_id="sales-demo-002")
    )

    records = crm_service.list_customer_followups("customer-demo-001")

    assert [record["followup_id"] for record in records] == [
        first.record["followup_id"],
        second.record["followup_id"],
    ]


def test_get_followup_returns_unicode_json(monkeypatch, tmp_path) -> None:
    database_path = initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    result = crm_service.create_followup(make_followup())

    record = crm_service.get_followup(result.record["followup_id"])
    assert record["analysis"]["needs"] == ["确认文档接入方式"]

    connection = database.get_connection()
    try:
        stored_json = connection.execute(
            "SELECT analysis_json FROM followup_records WHERE followup_id = ?",
            (result.record["followup_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert "客户计划评估内部知识库方案" in stored_json
    assert json.loads(stored_json)["needs"] == ["确认文档接入方式"]
    assert database_path.exists()


def test_get_and_list_reject_unknown_records(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)

    with pytest.raises(CRMNotFoundError, match="跟进记录"):
        crm_service.get_followup("followup-missing")

    with pytest.raises(CRMNotFoundError, match="客户"):
        crm_service.list_customer_followups("customer-missing")


def test_customer_response_uses_timezone_aware_datetimes(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    monkeypatch.setattr(
        crm_service,
        "_current_time",
        lambda: "2026-09-09T08:00:00+00:00",
    )

    customer = crm_service.upsert_customer(
        CRMCustomerUpsertRequest(
            customer_id="customer-demo-001",
            company_name="示例制造企业",
            industry=None,
            sales_owner="sales-demo",
        )
    )

    assert customer["created_at"].tzinfo == UTC


def test_crm_transaction_failure_rolls_back_customer_and_followup(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    connection = database.get_connection()
    try:
        connection.execute(
            """
            CREATE TRIGGER fail_followup_insert
            BEFORE INSERT ON followup_records
            BEGIN
                SELECT RAISE(ABORT, 'injected crm failure');
            END
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(Exception, match="injected crm failure"):
        crm_service.create_followup(make_followup())

    connection = database.get_connection()
    try:
        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]
        followup_count = connection.execute(
            "SELECT COUNT(*) FROM followup_records"
        ).fetchone()[0]
        stage = connection.execute(
            "SELECT processing_stage FROM workflow_runs"
        ).fetchone()[0]
    finally:
        connection.close()

    assert customer_count == 0
    assert followup_count == 0
    assert stage == "workflow_registered"


def test_notification_attempt_uses_stable_key_and_records_stage(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    created = crm_service.create_followup(
        make_followup(notification_mode="send")
    )

    attempt = crm_service.begin_notification_attempt(
        created.record["followup_id"]
    )
    record = crm_service.get_followup(created.record["followup_id"])
    connection = database.get_connection()
    try:
        stage = connection.execute(
            "SELECT processing_stage FROM workflow_runs WHERE run_id = ?",
            (created.record["run_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert attempt.notification_request_key == "sales-followup:run-demo-001"
    assert attempt.attempt_number == 1
    assert attempt.manual is False
    assert record["notification_attempt_count"] == 1
    assert record["notification_last_attempt_at"] is not None
    assert stage == "notification_requested"


def test_definite_notification_failure_preserves_crm_and_requires_manual_retry(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    created = crm_service.create_followup(
        make_followup(notification_mode="send")
    )
    followup_id = created.record["followup_id"]
    crm_service.begin_notification_attempt(followup_id)

    failed = crm_service.update_notification_result(
        followup_id,
        notification_status="failed",
        message_id=None,
        error_code="provider_rejected",
    )

    assert failed["customer_id"] == "customer-demo-001"
    assert failed["notification_status"] == "failed"
    assert failed["notification_error_code"] == "provider_rejected"
    with pytest.raises(CRMConflictError, match="人工决定"):
        crm_service.begin_notification_attempt(followup_id)

    retry = crm_service.begin_notification_attempt(followup_id, manual=True)
    assert retry.notification_request_key == attempt_key(failed)
    assert retry.attempt_number == 2


def attempt_key(record: dict) -> str:
    return record["notification_request_key"]


def test_delivery_unknown_blocks_resend_until_human_resolution(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    created = crm_service.create_followup(
        make_followup(notification_mode="send", notification_channel="wecom")
    )
    followup_id = created.record["followup_id"]
    crm_service.begin_notification_attempt(followup_id)
    unknown = crm_service.update_notification_result(
        followup_id,
        notification_status="delivery_unknown",
        message_id=None,
        error_code="read_timeout",
    )

    assert unknown["notification_status"] == "delivery_unknown"
    with pytest.raises(CRMConflictError, match="禁止自动重发"):
        crm_service.begin_notification_attempt(followup_id, manual=True)

    resolved = crm_service.resolve_unknown_notification(
        followup_id,
        delivered=False,
        message_id=None,
    )
    retry = crm_service.begin_notification_attempt(followup_id, manual=True)

    assert resolved["notification_status"] == "failed"
    assert resolved["notification_error_code"] == "human_confirmed_not_sent"
    assert resolved["notification_resolved_at"] is not None
    assert retry.attempt_number == 2


def test_notification_attempts_are_capped_at_three(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    created = crm_service.create_followup(
        make_followup(notification_mode="send")
    )
    followup_id = created.record["followup_id"]

    for attempt_number in range(1, 4):
        attempt = crm_service.begin_notification_attempt(
            followup_id,
            manual=attempt_number > 1,
        )
        assert attempt.attempt_number == attempt_number
        crm_service.update_notification_result(
            followup_id,
            notification_status="failed",
            message_id=None,
            error_code="provider_rejected",
        )

    with pytest.raises(CRMConflictError, match="最大人工发送次数"):
        crm_service.begin_notification_attempt(followup_id, manual=True)


def test_notification_terminal_result_is_idempotent_but_cannot_be_overwritten(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    created = crm_service.create_followup(
        make_followup(notification_mode="send")
    )
    followup_id = created.record["followup_id"]
    crm_service.begin_notification_attempt(followup_id)

    first = crm_service.update_notification_result(
        followup_id,
        notification_status="sent",
        message_id="message-001",
        error_code=None,
    )
    repeated = crm_service.update_notification_result(
        followup_id,
        notification_status="sent",
        message_id="message-001",
        error_code=None,
    )

    assert repeated == first
    with pytest.raises(CRMConflictError, match="不能覆盖"):
        crm_service.update_notification_result(
            followup_id,
            notification_status="delivery_unknown",
            message_id=None,
            error_code="timeout",
        )


@pytest.mark.parametrize(
    ("notification_status", "error_code", "resume_from", "reason_fragment"),
    [
        (
            "failed",
            "provider_rejected",
            "notification",
            "人工决定",
        ),
        (
            "delivery_unknown",
            "read_timeout",
            "human_delivery_check",
            "人工核对",
        ),
    ],
)
def test_notification_failure_recovery_preserves_crm_and_requires_human_action(
    monkeypatch,
    tmp_path,
    notification_status,
    error_code,
    resume_from,
    reason_fragment,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    insert_workflow_run()
    created = crm_service.create_followup(
        make_followup(notification_mode="send")
    )
    crm_service.begin_notification_attempt(created.record["followup_id"])
    crm_service.update_notification_result(
        created.record["followup_id"],
        notification_status=notification_status,
        message_id=None,
        error_code=error_code,
    )
    workflow_run_service.finish_workflow_run(
        run_id=created.record["run_id"],
        status="needs_human_review",
        output_data={
            "followup_id": created.record["followup_id"],
            "review_reasons": ["notification_requires_human_action"],
        },
        category="sales_followup",
        priority="high",
    )

    recovery = workflow_run_service.get_workflow_recovery(
        created.record["run_id"]
    )
    persisted = crm_service.get_followup(created.record["followup_id"])

    assert persisted["notification_status"] == notification_status
    assert persisted["customer_id"] == "customer-demo-001"
    assert recovery["resume_from"] == resume_from
    assert recovery["automatic_retry_allowed"] is False
    assert recovery["requires_human_action"] is True
    assert reason_fragment in recovery["reason"]
