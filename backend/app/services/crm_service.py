import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..database import get_connection
from ..models.crm import CRMCustomerUpsertRequest, CRMFollowupCreateRequest

SALES_FOLLOWUP_WORKFLOW = "sales-followup-assistant"
MAX_NOTIFICATION_ATTEMPTS = 3


class CRMNotFoundError(RuntimeError):
    pass


class CRMConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class CRMFollowupCreateResult:
    record: dict[str, Any]
    created: bool


@dataclass(frozen=True)
class CRMNotificationAttemptResult:
    followup_id: str
    notification_channel: str
    notification_request_key: str
    attempt_number: int
    manual: bool


def _current_time() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_optional_time(value: str | None) -> datetime | None:
    return None if value is None else _parse_time(value)


def _row_to_customer(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "customer_id": row["customer_id"],
        "company_name": row["company_name"],
        "industry": row["industry"],
        "sales_owner": row["sales_owner"],
        "created_at": _parse_time(row["created_at"]),
        "updated_at": _parse_time(row["updated_at"]),
    }


def _row_to_followup(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "followup_id": row["followup_id"],
        "customer_id": row["customer_id"],
        "run_id": row["run_id"],
        "event_id": row["event_id"],
        "requirement_snapshot": row["requirement_snapshot"],
        "analysis": json.loads(row["analysis_json"]),
        "priority": row["priority"],
        "review_status": row["review_status"],
        "review_reasons": json.loads(row["review_reasons_json"]),
        "notification_mode": row["notification_mode"],
        "notification_channel": row["notification_channel"],
        "notification_status": row["notification_status"],
        "notification_request_key": row["notification_request_key"],
        "notification_message_id": row["notification_message_id"],
        "notification_error_code": row["notification_error_code"],
        "notification_attempt_count": row["notification_attempt_count"],
        "notification_last_attempt_at": _parse_optional_time(
            row["notification_last_attempt_at"]
        ),
        "notification_resolved_at": _parse_optional_time(
            row["notification_resolved_at"]
        ),
        "created_at": _parse_time(row["created_at"]),
        "updated_at": _parse_time(row["updated_at"]),
    }


def _load_customer(
    connection: sqlite3.Connection,
    customer_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM customers WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    if row is None:
        raise CRMNotFoundError("找不到指定客户")
    return row


def _load_followup(
    connection: sqlite3.Connection,
    followup_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM followup_records WHERE followup_id = ?",
        (followup_id,),
    ).fetchone()
    if row is None:
        raise CRMNotFoundError("找不到指定跟进记录")
    return row


def _upsert_customer(
    connection: sqlite3.Connection,
    customer: CRMCustomerUpsertRequest,
    now: str,
) -> None:
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
        ON CONFLICT (customer_id) DO UPDATE SET
            company_name = excluded.company_name,
            industry = excluded.industry,
            sales_owner = excluded.sales_owner,
            updated_at = excluded.updated_at
        """,
        (
            customer.customer_id,
            customer.company_name,
            customer.industry,
            customer.sales_owner,
            now,
            now,
        ),
    )


def upsert_customer(
    customer: CRMCustomerUpsertRequest,
) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")
        _upsert_customer(connection, customer, now)
        row = _load_customer(connection, customer.customer_id)
        connection.commit()
        return _row_to_customer(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_customer(customer_id: str) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        return _row_to_customer(_load_customer(connection, customer_id))
    finally:
        connection.close()


def create_followup(
    request: CRMFollowupCreateRequest,
) -> CRMFollowupCreateResult:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            "SELECT * FROM followup_records WHERE run_id = ?",
            (request.run_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["customer_id"] != request.customer.customer_id
                or existing["event_id"] != request.event_id
            ):
                raise CRMConflictError("run_id 已关联其他客户或业务事件")

            connection.commit()
            return CRMFollowupCreateResult(
                record=_row_to_followup(existing),
                created=False,
            )

        workflow_run = connection.execute(
            """
            SELECT event_id, workflow_name, status
            FROM workflow_runs
            WHERE run_id = ?
            """,
            (request.run_id,),
        ).fetchone()
        if workflow_run is None:
            raise CRMNotFoundError("找不到对应的工作流运行")

        if (
            workflow_run["workflow_name"] != SALES_FOLLOWUP_WORKFLOW
            or workflow_run["event_id"] != request.event_id
        ):
            raise CRMConflictError("工作流运行与销售跟进请求不匹配")

        if workflow_run["status"] != "running":
            raise CRMConflictError("只有运行中的工作流可以创建跟进记录")

        now = _current_time()
        _upsert_customer(connection, request.customer, now)

        if request.review_status == "pending":
            notification_status = "skipped"
            notification_request_key = None
        elif request.notification_mode == "preview":
            notification_status = "preview"
            notification_request_key = f"sales-followup:{request.run_id}"
        else:
            notification_status = "pending"
            notification_request_key = f"sales-followup:{request.run_id}"

        followup_id = str(uuid4())
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
                request.customer.customer_id,
                request.run_id,
                request.event_id,
                request.requirement_snapshot,
                request.analysis.model_dump_json(),
                request.priority,
                request.review_status,
                json.dumps(request.review_reasons, ensure_ascii=False),
                request.notification_mode,
                request.notification_channel,
                notification_status,
                notification_request_key,
                now,
                now,
            ),
        )

        processing_stage = (
            "notification_recorded"
            if notification_status in {"preview", "skipped"}
            else "crm_saved"
        )
        connection.execute(
            """
            UPDATE workflow_runs
            SET processing_stage = ?,
                failure_stage = NULL,
                updated_at = ?
            WHERE run_id = ?
            """,
            (processing_stage, now, request.run_id),
        )

        created = _load_followup(connection, followup_id)
        connection.commit()
        return CRMFollowupCreateResult(
            record=_row_to_followup(created),
            created=True,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_followup(followup_id: str) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        return _row_to_followup(_load_followup(connection, followup_id))
    finally:
        connection.close()


def get_followup_by_run(run_id: str) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            "SELECT * FROM followup_records WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise CRMNotFoundError("找不到该工作流运行对应的跟进记录")
        return _row_to_followup(row)
    finally:
        connection.close()


def begin_notification_attempt(
    followup_id: str,
    *,
    manual: bool = False,
) -> CRMNotificationAttemptResult:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")
        record = _load_followup(connection, followup_id)

        if record["notification_mode"] != "send":
            raise CRMConflictError("只有 send 模式可以开始通知发送")
        if record["review_status"] != "not_required":
            raise CRMConflictError("等待人工复核的跟进记录不能发送通知")
        if record["notification_channel"] is None:
            raise CRMConflictError("跟进记录缺少通知渠道")
        if record["notification_request_key"] is None:
            raise CRMConflictError("跟进记录缺少稳定通知请求标识")

        current_status = record["notification_status"]
        attempt_count = record["notification_attempt_count"]

        if current_status == "delivery_unknown":
            raise CRMConflictError(
                "通知结果不确定，必须先人工核对，禁止自动重发"
            )
        if current_status == "failed" and not manual:
            raise CRMConflictError("通知明确失败后只能由人工决定重新发送")
        if current_status not in {"pending", "failed"}:
            raise CRMConflictError("当前通知状态不能开始发送")
        if current_status == "pending" and attempt_count > 0:
            raise CRMConflictError("通知请求已经开始，不能并发或重复发送")
        if attempt_count >= MAX_NOTIFICATION_ATTEMPTS:
            raise CRMConflictError("通知已经达到最大人工发送次数")

        next_attempt = attempt_count + 1
        connection.execute(
            """
            UPDATE followup_records
            SET notification_status = 'pending',
                notification_message_id = NULL,
                notification_error_code = NULL,
                notification_attempt_count = ?,
                notification_last_attempt_at = ?,
                notification_resolved_at = NULL,
                updated_at = ?
            WHERE followup_id = ?
            """,
            (next_attempt, now, now, followup_id),
        )
        connection.execute(
            """
            UPDATE workflow_runs
            SET processing_stage = 'notification_requested',
                failure_stage = NULL,
                updated_at = ?
            WHERE run_id = ?
            """,
            (now, record["run_id"]),
        )
        connection.commit()

        return CRMNotificationAttemptResult(
            followup_id=followup_id,
            notification_channel=record["notification_channel"],
            notification_request_key=record["notification_request_key"],
            attempt_number=next_attempt,
            manual=manual,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_notification_result(
    followup_id: str,
    *,
    notification_status: str,
    message_id: str | None,
    error_code: str | None,
) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")
        record = _load_followup(connection, followup_id)

        if record["notification_mode"] != "send":
            raise CRMConflictError("只有 send 模式可以保存通知结果")
        if record["notification_attempt_count"] < 1:
            raise CRMConflictError("必须先登记通知发送尝试")
        if record["notification_status"] != "pending":
            if (
                record["notification_status"] == notification_status
                and record["notification_message_id"] == message_id
                and record["notification_error_code"] == error_code
            ):
                connection.commit()
                return _row_to_followup(record)
            raise CRMConflictError("通知结果已经记录且不能覆盖")

        connection.execute(
            """
            UPDATE followup_records
            SET notification_status = ?,
                notification_message_id = ?,
                notification_error_code = ?,
                updated_at = ?
            WHERE followup_id = ?
            """,
            (
                notification_status,
                message_id,
                error_code,
                now,
                followup_id,
            ),
        )
        connection.execute(
            """
            UPDATE workflow_runs
            SET processing_stage = 'notification_recorded',
                updated_at = ?
            WHERE run_id = ?
            """,
            (now, record["run_id"]),
        )
        updated = _load_followup(connection, followup_id)
        connection.commit()
        return _row_to_followup(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def resolve_unknown_notification(
    followup_id: str,
    *,
    delivered: bool,
    message_id: str | None,
) -> dict[str, Any]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row
    now = _current_time()

    try:
        connection.execute("BEGIN IMMEDIATE")
        record = _load_followup(connection, followup_id)
        if record["notification_status"] != "delivery_unknown":
            raise CRMConflictError("只有 delivery_unknown 状态可以人工核对")

        if delivered:
            next_status = "sent"
            error_code = None
        else:
            next_status = "failed"
            message_id = None
            error_code = "human_confirmed_not_sent"

        connection.execute(
            """
            UPDATE followup_records
            SET notification_status = ?,
                notification_message_id = ?,
                notification_error_code = ?,
                notification_resolved_at = ?,
                updated_at = ?
            WHERE followup_id = ?
            """,
            (
                next_status,
                message_id,
                error_code,
                now,
                now,
                followup_id,
            ),
        )
        connection.execute(
            """
            UPDATE workflow_runs
            SET processing_stage = 'notification_recorded',
                updated_at = ?
            WHERE run_id = ?
            """,
            (now, record["run_id"]),
        )
        updated = _load_followup(connection, followup_id)
        connection.commit()
        return _row_to_followup(updated)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_customer_followups(customer_id: str) -> list[dict[str, Any]]:
    connection = get_connection()
    connection.row_factory = sqlite3.Row

    try:
        _load_customer(connection, customer_id)
        rows = connection.execute(
            """
            SELECT *
            FROM followup_records
            WHERE customer_id = ?
            ORDER BY created_at, id
            """,
            (customer_id,),
        ).fetchall()
        return [_row_to_followup(row) for row in rows]
    finally:
        connection.close()
