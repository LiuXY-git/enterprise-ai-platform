import sqlite3

import pytest

from backend.app import database

EXPECTED_COLUMNS = {
    "id",
    "run_id",
    "event_id",
    "workflow_name",
    "source",
    "requester",
    "report_date",
    "status",
    "category",
    "priority",
    "input_json",
    "output_json",
    "processing_stage",
    "checkpoint_json",
    "failure_stage",
    "error_type",
    "error_message",
    "n8n_execution_id",
    "retry_count",
    "duplicate_count",
    "elapsed_time",
    "total_tokens",
    "started_at",
    "finished_at",
    "created_at",
    "updated_at",
}


def initialize_temp_database(
    monkeypatch,
    tmp_path,
):
    database_path = tmp_path / "workflow-test.db"

    monkeypatch.setattr(
        database,
        "DATABASE_PATH",
        database_path,
    )

    database.init_database()
    database.init_database()

    return database_path


def test_init_database_creates_workflow_runs_table(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(
        monkeypatch,
        tmp_path,
    )

    connection = sqlite3.connect(database_path)

    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(workflow_runs)")
        }
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(workflow_runs)")
        }
    finally:
        connection.close()

    assert EXPECTED_COLUMNS <= columns
    assert "idx_workflow_runs_report_date" in indexes
    assert "idx_workflow_runs_status" in indexes
    assert "idx_workflow_runs_n8n_execution_id" in indexes


def test_workflow_runs_reject_duplicate_event(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = initialize_temp_database(
        monkeypatch,
        tmp_path,
    )

    connection = sqlite3.connect(database_path)

    insert_statement = """
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
    """

    first_run = (
        "run-001",
        "mail-day41-001",
        "W6D41 - Persistent AI Email Assistant",
        "mock-email",
        "customer-001",
        "2026-09-03",
        "running",
        "{}",
        "execution-001",
        "2026-09-03T09:00:00+08:00",
    )

    duplicate_run = (
        "run-002",
        "mail-day41-001",
        "W6D41 - Persistent AI Email Assistant",
        "mock-email",
        "customer-001",
        "2026-09-03",
        "running",
        "{}",
        "execution-002",
        "2026-09-03T09:01:00+08:00",
    )

    try:
        connection.execute(
            insert_statement,
            first_run,
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                insert_statement,
                duplicate_run,
            )
    finally:
        connection.close()
