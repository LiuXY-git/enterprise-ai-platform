import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..database import get_connection

MAX_RETRY_COUNT = 3
MAX_CHECKPOINT_BYTES = 16_384

_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(
        r"(?i)(api[_-]?key|token|secret|password)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
    re.compile(r"https?://[^\s]+", re.IGNORECASE),
)


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
    processing_stage: str = "workflow_registered"
    resume_from: str = "ai_analysis"
    checkpoint_data: dict[str, Any] | None = None


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

    serialized_checkpoint = record.pop("checkpoint_json", None)
    record["checkpoint_data"] = (
        None
        if serialized_checkpoint is None
        else json.loads(serialized_checkpoint)
    )

    return record


def _sanitize_error_message(message: str) -> str:
    sanitized = message
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized[:1000]


def _resume_from_stage(processing_stage: str) -> str:
    return {
        "workflow_registered": "ai_analysis",
        "analysis_completed": "crm_transaction",
        "crm_saved": "notification",
        "notification_requested": "human_delivery_check",
        "notification_recorded": "complete",
    }.get(processing_stage, "human_review")


def _checkpoint_from_row(row: sqlite3.Row) -> dict[str, Any] | None:
    serialized = row["checkpoint_json"]
    return None if serialized is None else json.loads(serialized)


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
                processing_stage="workflow_registered",
                resume_from="ai_analysis",
            )

        stored_input = json.loads(existing["input_json"])

        if replay:
            if existing["status"] != "failed":
                raise WorkflowRunConflictError("只有失败的工作流记录可以回放")

            if existing["retry_count"] >= MAX_RETRY_COUNT:
                raise WorkflowRunConflictError("工作流记录已经达到最大回放次数")

            if existing["processing_stage"] in {
                "crm_saved",
                "notification_requested",
                "notification_recorded",
            }:
                raise WorkflowRunConflictError(
                    "CRM already saved; use notification handling instead of replay"
                )

            retry_count = existing["retry_count"] + 1

            connection.execute(
                """
                UPDATE workflow_runs
                SET status = 'running',
                    category = NULL,
                    priority = NULL,
                    output_json = NULL,
                    failure_stage = NULL,
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
                processing_stage=existing["processing_stage"],
                resume_from=_resume_from_stage(existing["processing_stage"]),
                checkpoint_data=_checkpoint_from_row(existing),
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
            processing_stage=existing["processing_stage"],
            resume_from=_resume_from_stage(existing["processing_stage"]),
            checkpoint_data=_checkpoint_from_row(existing),
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_workflow_checkpoint(
    *,
    run_id: str,
    stage: str,
    checkpoint_data: dict[str, Any],
) -> dict[str, Any]:
    if stage != "analysis_completed":
        raise ValueError("当前仅允许保存 analysis_completed 检查点")

    serialized = json.dumps(
        checkpoint_data,
        ensure_ascii=False,
        sort_keys=True,
    )
    if len(serialized.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise ValueError("检查点数据不能超过 16384 字节")

    connection = get_connection()
    connection.row_factory = sqlite3.Row
    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = _load_run_by_id(connection, run_id)

        if existing["status"] != "running":
            raise WorkflowRunConflictError("只有运行中的工作流可以保存检查点")

        current_stage = existing["processing_stage"]
        if current_stage == stage:
            if existing["checkpoint_json"] != serialized:
                raise WorkflowRunConflictError("检查点已经保存且内容不一致")
            connection.commit()
            return _row_to_record(existing)

        if current_stage != "workflow_registered":
            raise WorkflowRunConflictError("工作流检查点不能回退或跳跃")

        connection.execute(
            """
            UPDATE workflow_runs
            SET processing_stage = ?,
                checkpoint_json = ?,
                failure_stage = NULL,
                updated_at = ?
            WHERE run_id = ?
            """,
            (stage, serialized, now, run_id),
        )
        updated = _load_run_by_id(connection, run_id)
        connection.commit()
        return _row_to_record(updated)
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
                failure_stage = NULL,
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


def _mark_failed(
    connection: sqlite3.Connection,
    *,
    existing: sqlite3.Row,
    error_type: str,
    error_message: str,
    failure_stage: str,
    now: str,
) -> sqlite3.Row:
    if existing["status"] == "failed":
        return existing

    if existing["status"] != "running":
        raise WorkflowRunConflictError(
            "只有运行中的工作流可以标记为失败"
        )

    connection.execute(
        """
        UPDATE workflow_runs
        SET status = 'failed',
            failure_stage = ?,
            error_type = ?,
            error_message = ?,
            finished_at = ?,
            updated_at = ?
        WHERE run_id = ?
        """,
        (
            failure_stage,
            error_type,
            _sanitize_error_message(error_message),
            now,
            now,
            existing["run_id"],
        ),
    )
    return _load_run_by_id(connection, existing["run_id"])


def fail_workflow_run(
    *,
    run_id: str,
    error_type: str,
    error_message: str,
    failure_stage: str = "unknown",
) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = _load_run_by_id(connection, run_id)
        updated = _mark_failed(
            connection,
            existing=existing,
            error_type=error_type,
            error_message=error_message,
            failure_stage=failure_stage,
            now=now,
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
    failure_stage: str = "unknown",
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

        updated = _mark_failed(
            connection,
            existing=existing,
            error_type=error_type,
            error_message=error_message,
            failure_stage=failure_stage,
            now=now,
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


def get_workflow_recovery(run_id: str) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        run = _load_run_by_id(connection, run_id)
        followup = connection.execute(
            "SELECT notification_status FROM followup_records WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        processing_stage = run["processing_stage"]
        resume_from = _resume_from_stage(processing_stage)
        requires_human_action = False
        automatic_retry_allowed = False

        if run["status"] == "succeeded":
            resume_from = "complete"
            reason = "工作流已经成功完成"
        elif (
            processing_stage == "notification_requested"
            or (
                followup is not None
                and followup["notification_status"] == "delivery_unknown"
            )
        ):
            resume_from = "human_delivery_check"
            requires_human_action = True
            reason = "通知结果不确定，必须先人工核对实际送达情况"
        elif (
            followup is not None
            and followup["notification_status"] == "failed"
        ):
            resume_from = "notification"
            requires_human_action = True
            reason = "通知明确失败，需要人工决定是否重新发送"
        elif processing_stage in {"crm_saved", "notification_recorded"}:
            requires_human_action = True
            reason = "CRM 已保存，通过通知接口处理或核对最终状态，禁止整条回放"
        elif run["status"] == "needs_human_review":
            resume_from = "human_review"
            requires_human_action = True
            reason = "工作流正在等待人工复核"
        elif run["status"] == "running":
            reason = "工作流仍在运行，不能并发恢复"
        elif run["retry_count"] >= MAX_RETRY_COUNT:
            requires_human_action = True
            reason = "工作流已经达到最大自动恢复次数"
        else:
            automatic_retry_allowed = resume_from in {
                "ai_analysis",
                "crm_transaction",
                "notification",
            }
            reason = "可以从最后一个安全检查点恢复"

        return {
            "run_id": run_id,
            "status": run["status"],
            "processing_stage": processing_stage,
            "resume_from": resume_from,
            "automatic_retry_allowed": automatic_retry_allowed,
            "requires_human_action": requires_human_action,
            "reason": reason,
            "retry_count": run["retry_count"],
            "checkpoint_data": _checkpoint_from_row(run),
        }
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
