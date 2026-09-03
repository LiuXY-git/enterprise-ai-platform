import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "enterprise_ai.db"


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    return sqlite3.connect(DATABASE_PATH)


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
