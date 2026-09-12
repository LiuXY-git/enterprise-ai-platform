import sqlite3

import pytest

from backend.app import database
from backend.app.services.workflow_run_service import (
    WorkflowRunConflictError,
    WorkflowRunNotFoundError,
    fail_workflow_run,
    fail_workflow_run_by_execution,
    finish_workflow_run,
    get_workflow_recovery,
    get_workflow_run,
    list_workflow_runs,
    save_workflow_checkpoint,
    start_workflow_run,
)


def initialize_temp_database(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "workflow-service-test.db"

    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        database_path,
    )
    database.init_database()

    return database_path


def start_test_run(
    *,
    execution_id: str,
    replay: bool = False,
):
    return start_workflow_run(
        event_id="mail-day41-001",
        workflow_name="W6D41 - Persistent AI Email Assistant",
        source="mock-email",
        requester="customer-001",
        report_date="2026-09-03",
        input_data={
            "event_id": "mail-day41-001",
            "subject": "文档格式咨询",
        },
        n8n_execution_id=execution_id,
        replay=replay,
    )


def mark_run_failed(
    database_path,
) -> None:
    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            UPDATE workflow_runs
            SET status = 'failed'
            WHERE event_id = 'mail-day41-001'
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_start_workflow_run_creates_running_record(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(
        monkeypatch,
        tmp_path,
    )

    result = start_test_run(
        execution_id="execution-001",
    )

    assert result.status == "running"
    assert result.should_process is True
    assert result.duplicate is False
    assert result.replayed is False
    assert result.retry_count == 0
    assert result.processing_stage == "workflow_registered"
    assert result.resume_from == "ai_analysis"
    assert result.checkpoint_data is None

    connection = sqlite3.connect(database_path)

    try:
        row = connection.execute(
            """
            SELECT status, retry_count, duplicate_count
            FROM workflow_runs
            """
        ).fetchone()
    finally:
        connection.close()

    assert row == (
        "running",
        0,
        0,
    )


def test_start_workflow_run_blocks_duplicate_event(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(
        monkeypatch,
        tmp_path,
    )

    first = start_test_run(
        execution_id="execution-001",
    )
    duplicate = start_test_run(
        execution_id="execution-002",
    )

    assert duplicate.run_id == first.run_id
    assert duplicate.should_process is False
    assert duplicate.duplicate is True
    assert duplicate.duplicate_count == 1

    connection = sqlite3.connect(database_path)

    try:
        count = connection.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
    finally:
        connection.close()

    assert count == 1


def test_replay_requires_failed_status(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    start_test_run(
        execution_id="execution-001",
    )

    with pytest.raises(
        WorkflowRunConflictError,
        match="只有失败",
    ):
        start_test_run(
            execution_id="execution-002",
            replay=True,
        )


def test_failed_run_can_be_replayed_three_times(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    first = start_test_run(
        execution_id="execution-001",
    )

    for attempt in range(1, 4):
        mark_run_failed(database_path)

        replay = start_test_run(
            execution_id=f"execution-replay-{attempt}",
            replay=True,
        )

        assert replay.run_id == first.run_id
        assert replay.should_process is True
        assert replay.replayed is True
        assert replay.retry_count == attempt

    mark_run_failed(database_path)

    with pytest.raises(
        WorkflowRunConflictError,
        match="最大回放次数",
    ):
        start_test_run(
            execution_id="execution-replay-4",
            replay=True,
        )


def test_replay_uses_original_input(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    start_test_run(
        execution_id="execution-001",
    )
    mark_run_failed(database_path)

    replay = start_workflow_run(
        event_id="mail-day41-001",
        workflow_name="W6D41 - Persistent AI Email Assistant",
        source="changed-source",
        requester="changed-user",
        report_date="2026-09-04",
        input_data={
            "event_id": "mail-day41-001",
            "subject": "被修改的内容",
        },
        n8n_execution_id="execution-replay-1",
        replay=True,
    )

    assert replay.input_data == {
        "event_id": "mail-day41-001",
        "subject": "文档格式咨询",
    }


def test_finish_workflow_run_saves_output(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    started = start_test_run(
        execution_id="execution-001",
    )

    finished = finish_workflow_run(
        run_id=started.run_id,
        status="succeeded",
        output_data={
            "answer": "支持 PDF、DOCX 和 Markdown。",
        },
        category="product",
        priority="normal",
        elapsed_time=1.5,
        total_tokens=120,
    )

    assert finished["status"] == "succeeded"
    assert finished["category"] == "product"
    assert finished["elapsed_time"] == 1.5
    assert finished["total_tokens"] == 120
    assert finished["output_data"] == {
        "answer": "支持 PDF、DOCX 和 Markdown。",
    }
    assert finished["finished_at"] is not None


def test_finished_run_cannot_finish_again(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    started = start_test_run(
        execution_id="execution-001",
    )

    finish_workflow_run(
        run_id=started.run_id,
        status="succeeded",
        output_data={"answer": "第一次结果"},
    )

    with pytest.raises(
        WorkflowRunConflictError,
        match="只有运行中",
    ):
        finish_workflow_run(
            run_id=started.run_id,
            status="succeeded",
            output_data={"answer": "第二次结果"},
        )


def test_failure_is_saved_by_execution_id(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    started = start_test_run(
        execution_id="execution-001",
    )

    failed = fail_workflow_run_by_execution(
        n8n_execution_id="execution-001",
        error_type="timeout",
        error_message="AI request timed out",
    )

    assert failed["run_id"] == started.run_id
    assert failed["status"] == "failed"
    assert failed["error_type"] == "timeout"
    assert failed["error_message"] == (
        "AI request timed out"
    )
    assert failed["finished_at"] is not None

    repeated = fail_workflow_run_by_execution(
        n8n_execution_id="execution-001",
        error_type="timeout",
        error_message="AI request timed out",
    )

    assert repeated["run_id"] == started.run_id
    assert repeated["finished_at"] == failed["finished_at"]


def test_get_workflow_run_rejects_unknown_id(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(
        monkeypatch,
        tmp_path,
    )

    with pytest.raises(
        WorkflowRunNotFoundError,
        match="找不到指定",
    ):
        get_workflow_run("missing-run")


def test_list_workflow_runs_filters_report_date(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(
        monkeypatch,
        tmp_path,
    )
    first = start_test_run(
        execution_id="execution-001",
    )

    start_workflow_run(
        event_id="mail-day41-002",
        workflow_name="W6D41 - Persistent AI Email Assistant",
        source="mock-email",
        requester="customer-002",
        report_date="2026-09-04",
        input_data={
            "event_id": "mail-day41-002",
        },
        n8n_execution_id="execution-002",
    )

    records = list_workflow_runs(
        report_date="2026-09-03",
    )

    assert len(records) == 1
    assert records[0]["run_id"] == first.run_id
    assert records[0]["event_id"] == "mail-day41-001"


def test_analysis_checkpoint_is_idempotent_and_replay_resumes_after_it(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    started = start_test_run(execution_id="execution-001")
    analysis = {
        "summary": "客户希望确认部署方式。",
        "needs": ["确认部署方式"],
        "missing_information": [],
        "next_actions": ["安排技术沟通"],
        "risk_flags": [],
    }

    saved = save_workflow_checkpoint(
        run_id=started.run_id,
        stage="analysis_completed",
        checkpoint_data=analysis,
    )
    repeated = save_workflow_checkpoint(
        run_id=started.run_id,
        stage="analysis_completed",
        checkpoint_data=analysis,
    )
    fail_workflow_run(
        run_id=started.run_id,
        error_type="crm_unavailable",
        error_message="CRM service unavailable",
        failure_stage="crm_transaction",
    )
    replay = start_test_run(
        execution_id="execution-replay-001",
        replay=True,
    )

    assert saved["processing_stage"] == "analysis_completed"
    assert repeated["checkpoint_data"] == analysis
    assert replay.processing_stage == "analysis_completed"
    assert replay.resume_from == "crm_transaction"
    assert replay.checkpoint_data == analysis


def test_checkpoint_rejects_changed_content_and_invalid_transition(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    started = start_test_run(execution_id="execution-001")
    save_workflow_checkpoint(
        run_id=started.run_id,
        stage="analysis_completed",
        checkpoint_data={"summary": "first"},
    )

    with pytest.raises(WorkflowRunConflictError, match="内容不一致"):
        save_workflow_checkpoint(
            run_id=started.run_id,
            stage="analysis_completed",
            checkpoint_data={"summary": "changed"},
        )

    with pytest.raises(ValueError, match="仅允许"):
        save_workflow_checkpoint(
            run_id=started.run_id,
            stage="crm_saved",
            checkpoint_data={},
        )


def test_failure_sanitizes_secrets_and_records_stage(
    monkeypatch,
    tmp_path,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    started = start_test_run(execution_id="execution-001")

    failed = fail_workflow_run(
        run_id=started.run_id,
        error_type="ai_unavailable",
        error_message=(
            "Bearer secret-token api_key=super-secret "
            "https://provider.example/private"
        ),
        failure_stage="ai_analysis",
    )

    assert failed["failure_stage"] == "ai_analysis"
    assert "secret-token" not in failed["error_message"]
    assert "super-secret" not in failed["error_message"]
    assert "provider.example" not in failed["error_message"]
    assert failed["error_message"].count("[REDACTED]") == 3


def test_invalid_ai_output_can_finish_for_review_without_crm_write(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(monkeypatch, tmp_path)
    started = start_test_run(execution_id="execution-001")

    finished = finish_workflow_run(
        run_id=started.run_id,
        status="needs_human_review",
        output_data={
            "review_reasons": ["invalid_ai_output"],
            "safe_error": "AI 输出结构不符合约束",
        },
        category="sales_followup",
        priority="high",
    )

    connection = sqlite3.connect(database_path)
    try:
        followup_count = connection.execute(
            "SELECT COUNT(*) FROM followup_records"
        ).fetchone()[0]
    finally:
        connection.close()

    assert finished["status"] == "needs_human_review"
    assert finished["error_message"] is None
    assert followup_count == 0


def test_recovery_uses_last_safe_checkpoint_and_enforces_retry_limit(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(monkeypatch, tmp_path)
    started = start_test_run(execution_id="execution-001")
    save_workflow_checkpoint(
        run_id=started.run_id,
        stage="analysis_completed",
        checkpoint_data={"summary": "validated"},
    )
    fail_workflow_run(
        run_id=started.run_id,
        error_type="crm_transaction_failed",
        error_message="CRM transaction failed",
        failure_stage="crm_transaction",
    )

    recovery = get_workflow_recovery(started.run_id)
    assert recovery["resume_from"] == "crm_transaction"
    assert recovery["automatic_retry_allowed"] is True
    assert recovery["requires_human_action"] is False

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "UPDATE workflow_runs SET retry_count = 3 WHERE run_id = ?",
            (started.run_id,),
        )
        connection.commit()
    finally:
        connection.close()

    exhausted = get_workflow_recovery(started.run_id)
    assert exhausted["automatic_retry_allowed"] is False
    assert exhausted["requires_human_action"] is True


@pytest.mark.parametrize(
    "stage",
    ["crm_saved", "notification_requested", "notification_recorded"],
)
def test_replay_cannot_restart_a_run_after_crm_is_saved(
    monkeypatch, tmp_path, stage,
) -> None:
    database_path = initialize_temp_database(monkeypatch, tmp_path)
    started = start_test_run(execution_id="execution-notification")
    fail_workflow_run(
        run_id=started.run_id,
        error_type="notification_failed",
        error_message="Simulated notification failure",
        failure_stage="notification",
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE workflow_runs SET processing_stage = ? WHERE run_id = ?",
            (stage, started.run_id),
        )
    before = get_workflow_run(started.run_id)
    with pytest.raises(WorkflowRunConflictError, match="CRM already saved"):
        start_test_run(execution_id="execution-retry", replay=True)
    after = get_workflow_run(started.run_id)
    assert after == before
    recovery = get_workflow_recovery(started.run_id)
    assert recovery["automatic_retry_allowed"] is False
    assert recovery["requires_human_action"] is True
