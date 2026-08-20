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
