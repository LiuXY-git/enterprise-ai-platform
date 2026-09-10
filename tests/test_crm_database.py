import sqlite3

import pytest

from backend.app import database

CUSTOMER_COLUMNS = {
    "id",
    "customer_id",
    "company_name",
    "industry",
    "sales_owner",
    "created_at",
    "updated_at",
}

FOLLOWUP_COLUMNS = {
    "id",
    "followup_id",
    "customer_id",
    "run_id",
    "event_id",
    "requirement_snapshot",
    "analysis_json",
    "priority",
    "review_status",
    "review_reasons_json",
    "notification_mode",
    "notification_channel",
    "notification_status",
    "notification_request_key",
    "notification_message_id",
    "notification_error_code",
    "created_at",
    "updated_at",
}


def initialize_temp_database(monkeypatch, tmp_path):
    database_path = tmp_path / "crm-test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)

    database.init_database()
    database.init_database()

    return database_path


def insert_workflow_run(connection, *, run_id="run-demo-001") -> None:
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
            f"event-{run_id}",
            "sales-followup-assistant",
            "manual_demo",
            "sales-demo",
            "2026-09-09",
            "running",
            "{}",
            f"execution-{run_id}",
            "2026-09-09T08:00:00+00:00",
        ),
    )


def insert_customer(connection, *, customer_id="customer-demo-001") -> None:
    connection.execute(
        """
        INSERT INTO customers (
            customer_id,
            company_name,
            industry,
            sales_owner,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            "示例制造企业",
            "制造业",
            "sales-demo",
            "2026-09-09T08:00:00+00:00",
            "2026-09-09T08:00:00+00:00",
        ),
    )


def insert_followup(
    connection,
    *,
    followup_id="followup-demo-001",
    customer_id="customer-demo-001",
    run_id="run-demo-001",
    priority="high",
    notification_status="preview",
    notification_request_key="sales-followup:run-demo-001",
) -> None:
    connection.execute(
        """
        INSERT INTO followup_records (
            followup_id,
            customer_id,
            run_id,
            event_id,
            requirement_snapshot,
            analysis_json,
            priority,
            review_status,
            review_reasons_json,
            notification_mode,
            notification_channel,
            notification_status,
            notification_request_key,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            followup_id,
            customer_id,
            run_id,
            f"event-{run_id}",
            "希望建设内部知识库",
            "{}",
            priority,
            "not_required",
            "[]",
            "preview",
            "feishu",
            notification_status,
            notification_request_key,
            "2026-09-09T08:00:00+00:00",
            "2026-09-09T08:00:00+00:00",
        ),
    )


def test_get_connection_enables_foreign_keys(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)

    connection = database.get_connection()
    try:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert enabled == 1


def test_init_database_creates_crm_tables_and_indexes(monkeypatch, tmp_path) -> None:
    database_path = initialize_temp_database(monkeypatch, tmp_path)
    connection = sqlite3.connect(database_path)

    try:
        customer_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(customers)")
        }
        followup_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(followup_records)")
        }
        customer_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(customers)")
        }
        followup_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(followup_records)")
        }
    finally:
        connection.close()

    assert CUSTOMER_COLUMNS <= customer_columns
    assert FOLLOWUP_COLUMNS <= followup_columns
    assert "idx_customers_sales_owner" in customer_indexes
    assert "idx_followup_records_customer_id" in followup_indexes
    assert "idx_followup_records_event_id" in followup_indexes
    assert "idx_followup_records_notification_status" in followup_indexes
    assert "idx_followup_records_notification_request_key" in followup_indexes


def test_customer_id_is_unique(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    connection = database.get_connection()

    try:
        insert_customer(connection)
        with pytest.raises(sqlite3.IntegrityError):
            insert_customer(connection)
    finally:
        connection.close()


def test_followup_requires_existing_customer_and_run(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    connection = database.get_connection()

    try:
        with pytest.raises(sqlite3.IntegrityError):
            insert_followup(connection)

        insert_customer(connection)
        with pytest.raises(sqlite3.IntegrityError):
            insert_followup(connection)

        insert_workflow_run(connection)
        insert_followup(connection)
        connection.commit()

        count = connection.execute(
            "SELECT COUNT(*) FROM followup_records"
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 1


def test_followup_run_id_is_unique(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    connection = database.get_connection()

    try:
        insert_customer(connection)
        insert_workflow_run(connection)
        insert_followup(connection)

        with pytest.raises(sqlite3.IntegrityError):
            insert_followup(
                connection,
                followup_id="followup-demo-002",
                notification_request_key="sales-followup:run-demo-002",
            )
    finally:
        connection.close()


def test_notification_request_key_is_unique(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    connection = database.get_connection()

    try:
        insert_customer(connection)
        insert_workflow_run(connection)
        insert_workflow_run(connection, run_id="run-demo-002")
        insert_followup(connection)

        with pytest.raises(sqlite3.IntegrityError):
            insert_followup(
                connection,
                followup_id="followup-demo-002",
                run_id="run-demo-002",
                notification_request_key="sales-followup:run-demo-001",
            )
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("priority", "urgent"),
        ("notification_status", "unknown"),
    ],
)
def test_followup_rejects_invalid_checked_values(
    monkeypatch,
    tmp_path,
    field,
    value,
) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    connection = database.get_connection()

    try:
        insert_customer(connection)
        insert_workflow_run(connection)
        arguments = {field: value}

        with pytest.raises(sqlite3.IntegrityError):
            insert_followup(connection, **arguments)
    finally:
        connection.close()


def test_referenced_customer_and_run_cannot_be_deleted(monkeypatch, tmp_path) -> None:
    initialize_temp_database(monkeypatch, tmp_path)
    connection = database.get_connection()

    try:
        insert_customer(connection)
        insert_workflow_run(connection)
        insert_followup(connection)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM customers WHERE customer_id = ?",
                ("customer-demo-001",),
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM workflow_runs WHERE run_id = ?",
                ("run-demo-001",),
            )
    finally:
        connection.close()
