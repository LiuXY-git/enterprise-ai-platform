import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..database import get_connection
from ..models.crm import CRMCustomerUpsertRequest, CRMFollowupCreateRequest

SALES_FOLLOWUP_WORKFLOW = "sales-followup-assistant"


class CRMNotFoundError(RuntimeError):
    pass


class CRMConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class CRMFollowupCreateResult:
    record: dict[str, Any]
    created: bool


def _current_time() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


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
