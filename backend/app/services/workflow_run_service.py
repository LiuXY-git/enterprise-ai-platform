import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..database import get_connection

MAX_RETRY_COUNT = 3


class WorkflowRunConflictError(RuntimeError):
    pass


class WorkflowRunNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkflowRunStartResult:
    run_id: str
    status: str
    should_process: bool
    duplicate: bool
    replayed: bool
    retry_count: int
    duplicate_count: int
    input_data: dict[str, Any]


def _current_time() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(
    row: sqlite3.Row,
) -> dict[str, Any]:
    record = dict(row)

    record["input_data"] = json.loads(
        record.pop("input_json")
    )

    serialized_output = record.pop("output_json")
    record["output_data"] = (
        None
        if serialized_output is None
        else json.loads(serialized_output)
    )

    return record


def _load_run_by_id(
    connection: sqlite3.Connection,
    run_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM workflow_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()

    if row is None:
        raise WorkflowRunNotFoundError(
            "找不到指定的工作流记录"
        )

    return row


def start_workflow_run(
    *,
    event_id: str,
    workflow_name: str,
    source: str,
    requester: str,
    report_date: str,
    input_data: dict[str, Any],
    n8n_execution_id: str,
    replay: bool = False,
) -> WorkflowRunStartResult:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    now = _current_time()
    serialized_input = json.dumps(
        input_data,
        ensure_ascii=False,
        sort_keys=True,
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT *
            FROM workflow_runs
            WHERE workflow_name = ?
              AND event_id = ?
            """,
            (
                workflow_name,
                event_id,
            ),
        ).fetchone()

        if existing is None:
            if replay:
                raise WorkflowRunConflictError("找不到可以回放的失败记录")

            run_id = str(uuid4())

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
                    source,
                    requester,
                    report_date,
                    "running",
                    serialized_input,
                    n8n_execution_id,
                    now,
                ),
            )
            connection.commit()

            return WorkflowRunStartResult(
                run_id=run_id,
                status="running",
                should_process=True,
                duplicate=False,
                replayed=False,
                retry_count=0,
                duplicate_count=0,
                input_data=input_data,
            )

        stored_input = json.loads(existing["input_json"])

        if replay:
            if existing["status"] != "failed":
                raise WorkflowRunConflictError("只有失败的工作流记录可以回放")

            if existing["retry_count"] >= MAX_RETRY_COUNT:
                raise WorkflowRunConflictError("工作流记录已经达到最大回放次数")

            retry_count = existing["retry_count"] + 1

            connection.execute(
                """
                UPDATE workflow_runs
                SET status = 'running',
                    category = NULL,
                    priority = NULL,
                    output_json = NULL,
                    error_type = NULL,
                    error_message = NULL,
                    n8n_execution_id = ?,
                    retry_count = ?,
                    elapsed_time = NULL,
                    total_tokens = NULL,
                    started_at = ?,
                    finished_at = NULL,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (
                    n8n_execution_id,
                    retry_count,
                    now,
                    now,
                    existing["run_id"],
                ),
            )
            connection.commit()

            return WorkflowRunStartResult(
                run_id=existing["run_id"],
                status="running",
                should_process=True,
                duplicate=False,
                replayed=True,
                retry_count=retry_count,
                duplicate_count=existing["duplicate_count"],
                input_data=stored_input,
            )

        duplicate_count = existing["duplicate_count"] + 1

        connection.execute(
            """
            UPDATE workflow_runs
            SET duplicate_count = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                duplicate_count,
                now,
                existing["run_id"],
            ),
        )
        connection.commit()

        return WorkflowRunStartResult(
            run_id=existing["run_id"],
            status=existing["status"],
            should_process=False,
            duplicate=True,
            replayed=False,
            retry_count=existing["retry_count"],
            duplicate_count=duplicate_count,
            input_data=stored_input,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def finish_workflow_run(
    *,
    run_id: str,
    status: str,
    output_data: dict[str, Any],
    category: str | None = None,
    priority: str | None = None,
    elapsed_time: float | None = None,
    total_tokens: int | None = None,
) -> dict[str, Any]:
    allowed_statuses = {
        "succeeded",
        "needs_human_review",
    }

    if status not in allowed_statuses:
        raise ValueError(
            "完成状态必须是 succeeded 或 needs_human_review"
        )

    connection = get_connection()
    connection.row_factory = sqlite3.Row

    now = _current_time()
    serialized_output = json.dumps(
        output_data,
        ensure_ascii=False,
        sort_keys=True,
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = _load_run_by_id(
            connection,
            run_id,
        )

        if existing["status"] != "running":
            raise WorkflowRunConflictError(
                "只有运行中的工作流可以完成"
            )

        connection.execute(
            """
            UPDATE workflow_runs
            SET status = ?,
                category = ?,
                priority = ?,
                output_json = ?,
                error_type = NULL,
                error_message = NULL,
                elapsed_time = ?,
                total_tokens = ?,
                finished_at = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                status,
                category,
                priority,
                serialized_output,
                elapsed_time,
                total_tokens,
                now,
                now,
                run_id,
            ),
        )

        updated = _load_run_by_id(
            connection,
            run_id,
        )
        connection.commit()

        return _row_to_record(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fail_workflow_run_by_execution(
    *,
    n8n_execution_id: str,
    error_type: str,
    error_message: str,
) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT *
            FROM workflow_runs
            WHERE n8n_execution_id = ?
            """,
            (n8n_execution_id,),
        ).fetchone()

        if existing is None:
            raise WorkflowRunNotFoundError(
                "找不到对应的 n8n 执行记录"
            )

        if existing["status"] == "failed":
            connection.commit()
            return _row_to_record(existing)

        if existing["status"] != "running":
            raise WorkflowRunConflictError(
                "只有运行中的工作流可以标记为失败"
            )

        connection.execute(
            """
            UPDATE workflow_runs
            SET status = 'failed',
                error_type = ?,
                error_message = ?,
                finished_at = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                error_type,
                error_message[:1000],
                now,
                now,
                existing["run_id"],
            ),
        )

        updated = _load_run_by_id(
            connection,
            existing["run_id"],
        )
        connection.commit()

        return _row_to_record(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_workflow_run(
    run_id: str,
) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        row = _load_run_by_id(
            connection,
            run_id,
        )
        return _row_to_record(row)
    finally:
        connection.close()


def list_workflow_runs(
    *,
    report_date: str,
) -> list[dict[str, Any]]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM workflow_runs
            WHERE report_date = ?
            ORDER BY started_at, id
            """,
            (report_date,),
        ).fetchall()

        return [
            _row_to_record(row)
            for row in rows
        ]
    finally:
        connection.close()
