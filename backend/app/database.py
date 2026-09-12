import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "enterprise_ai.db"


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_column(
    connection: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table})")
    }
    if column not in columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_database() -> None:
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL,
                workflow_name TEXT NOT NULL,
                source TEXT NOT NULL,
                requester TEXT NOT NULL,
                report_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN (
                        'running',
                        'succeeded',
                        'failed',
                        'needs_human_review'
                    )
                ),
                category TEXT,
                priority TEXT,
                input_json TEXT NOT NULL,
                output_json TEXT,
                processing_stage TEXT NOT NULL DEFAULT 'workflow_registered',
                checkpoint_json TEXT,
                failure_stage TEXT,
                error_type TEXT,
                error_message TEXT,
                n8n_execution_id TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0
                    CHECK (retry_count >= 0),
                duplicate_count INTEGER NOT NULL DEFAULT 0
                    CHECK (duplicate_count >= 0),
                elapsed_time REAL,
                total_tokens INTEGER,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (workflow_name, event_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_workflow_runs_report_date
            ON workflow_runs (report_date)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_workflow_runs_status
            ON workflow_runs (status)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_workflow_runs_n8n_execution_id
            ON workflow_runs (n8n_execution_id)
            WHERE n8n_execution_id IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL UNIQUE,
                company_name TEXT NOT NULL,
                industry TEXT,
                sales_owner TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_customers_sales_owner
            ON customers (sales_owner)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS followup_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                followup_id TEXT NOT NULL UNIQUE,
                customer_id TEXT NOT NULL,
                run_id TEXT NOT NULL UNIQUE,
                event_id TEXT NOT NULL,
                requirement_snapshot TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                priority TEXT NOT NULL CHECK (
                    priority IN ('high', 'normal')
                ),
                review_status TEXT NOT NULL CHECK (
                    review_status IN ('not_required', 'pending')
                ),
                review_reasons_json TEXT NOT NULL,
                notification_mode TEXT NOT NULL CHECK (
                    notification_mode IN ('preview', 'send')
                ),
                notification_channel TEXT CHECK (
                    notification_channel IN ('feishu', 'wecom')
                ),
                notification_status TEXT NOT NULL CHECK (
                    notification_status IN (
                        'pending',
                        'preview',
                        'sent',
                        'failed',
                        'delivery_unknown',
                        'skipped'
                    )
                ),
                notification_request_key TEXT,
                notification_message_id TEXT,
                notification_error_code TEXT,
                notification_attempt_count INTEGER NOT NULL DEFAULT 0
                    CHECK (notification_attempt_count >= 0),
                notification_last_attempt_at TEXT,
                notification_resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (customer_id)
                    REFERENCES customers (customer_id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (run_id)
                    REFERENCES workflow_runs (run_id)
                    ON DELETE RESTRICT
            )
            """
        )
        _ensure_column(
            connection,
            table="workflow_runs",
            column="processing_stage",
            definition="TEXT NOT NULL DEFAULT 'workflow_registered'",
        )
        _ensure_column(
            connection,
            table="workflow_runs",
            column="checkpoint_json",
            definition="TEXT",
        )
        _ensure_column(
            connection,
            table="workflow_runs",
            column="failure_stage",
            definition="TEXT",
        )
        _ensure_column(
            connection,
            table="followup_records",
            column="notification_attempt_count",
            definition="INTEGER NOT NULL DEFAULT 0",
        )
        _ensure_column(
            connection,
            table="followup_records",
            column="notification_last_attempt_at",
            definition="TEXT",
        )
        _ensure_column(
            connection,
            table="followup_records",
            column="notification_resolved_at",
            definition="TEXT",
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_followup_records_customer_id
            ON followup_records (customer_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_followup_records_event_id
            ON followup_records (event_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_followup_records_notification_status
            ON followup_records (notification_status)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_followup_records_notification_request_key
            ON followup_records (notification_request_key)
            WHERE notification_request_key IS NOT NULL
            """
        )
        connection.commit()
    finally:
        connection.close()


def create_document(
    *,
    filename: str,
    file_type: str,
    content_type: str,
    size: int,
    status: str,
) -> int:
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                filename,
                file_type,
                content_type,
                size,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                filename,
                file_type,
                content_type,
                size,
                status,
            ),
        )
        connection.commit()

        document_id = cursor.lastrowid

        if document_id is None:
            raise RuntimeError("无法获取文档 ID")

        return document_id
    finally:
        connection.close()


def update_document_status(
    *,
    document_id: int,
    status: str,
) -> None:
    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE documents
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                document_id,
            ),
        )

        if cursor.rowcount == 0:
            raise RuntimeError("找不到需要更新的文档")

        connection.commit()
    finally:
        connection.close()
