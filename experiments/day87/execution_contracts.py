"""Execution evidence is distinct from business outcomes and evaluation scores."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from experiments.day85.contracts import (
    Count,
    Identifier,
    Sha256,
    StrictContract,
    canonical_hash,
)
from experiments.day86.dataset_contracts import DatasetPlan

BusinessStatus = Literal[
    "completed", "no_data", "needs_clarification", "failed", "rejected"
]


class Observations(StrictContract):
    business_status: BusinessStatus
    task_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    agent_run_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    stop_reason: Annotated[str, Field(min_length=1, max_length=80)]
    answer: str | None
    answer_source: str
    tool_attempts: Count
    mcp_dispatches: Count
    tool_retries: Count
    model_attempts: Count
    model_retries: Count
    model_requests: Count
    degraded: bool
    database_unchanged: bool
    approval_status: str | None
    simulated_effects: Count
    external_send: bool
    event_count: Count


class WorkerResult(StrictContract):
    protocol: Literal["day87-worker-v1"]
    case_id: Identifier
    case: Literal["monthly", "customer", "empty", "clarification"]
    scenario: str
    observations: Observations


class ExecutionMetrics(StrictContract):
    latency_ms: None = None
    input_tokens: None = None
    output_tokens: None = None
    cost: None = None
    notice: Literal["not_collected_day87"] = "not_collected_day87"


class ExecutionRow(StrictContract):
    case_id: Identifier
    execution_status: Literal[
        "not_run", "running", "completed", "error", "timeout", "interrupted"
    ]
    observed: Observations | None = None
    error: (
        Literal[
            "worker_start_failed",
            "worker_exit_nonzero",
            "worker_output_invalid",
            "case_timeout",
            "user_interrupted",
            "cleanup_failed",
        ]
        | None
    ) = None
    worker_exit_code: int | None = None
    cleanup_verified: bool | None = None
    judgement: Literal["not_evaluated"] = "not_evaluated"
    metrics: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    artifacts: dict[str, Sha256] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_outcome(self) -> Self:
        if self.execution_status == "completed":
            if (
                self.observed is None
                or self.error is not None
                or self.worker_exit_code != 0
            ):
                raise ValueError("completed_execution_requires_worker_evidence")
        elif self.observed is not None:
            raise ValueError("incomplete_execution_cannot_claim_observations")
        if (
            self.execution_status in {"error", "timeout", "interrupted"}
            and self.error is None
        ):
            raise ValueError("execution_failure_requires_error")
        if self.execution_status in {"not_run", "running"} and (
            self.error is not None or self.worker_exit_code is not None
        ):
            raise ValueError("unfinished_execution_has_terminal_fields")
        return self


class RunSummary(StrictContract):
    selected: Count
    completed: Count
    errors: Count
    timeouts: Count
    interrupted: Count
    not_run: Count
    running: Count
    business_status_counts: dict[str, Count]
    success_rate: None = None


class ExecutionReport(StrictContract):
    schema_version: Literal["day87-execution-v1"]
    report_kind: Literal["execution_record_not_scored_evaluation"]
    run_status: Literal["running", "completed", "completed_with_errors", "interrupted"]
    plan: DatasetPlan
    plan_sha256: Sha256
    timeout_seconds: Annotated[int, Field(ge=5, le=120)]
    execution_mode: Literal["fixture_model_real_local_mcp"]
    rows: list[ExecutionRow]
    summary: RunSummary
    source_sha256_lf: dict[str, Sha256]
    frozen_integrity: dict

    @model_validator(mode="after")
    def coherent_run(self) -> Self:
        from collections import Counter

        if self.plan_sha256 != canonical_hash(self.plan.model_dump()):
            raise ValueError("plan_hash_mismatch")
        if [r.case_id for r in self.rows] != [r.case_id for r in self.plan.rows]:
            raise ValueError("execution_coverage_mismatch")
        counts = Counter(r.execution_status for r in self.rows)
        business = dict(
            Counter(
                r.observed.business_status for r in self.rows if r.observed is not None
            )
        )
        expected = dict(
            selected=len(self.rows),
            completed=counts["completed"],
            errors=counts["error"],
            timeouts=counts["timeout"],
            interrupted=counts["interrupted"],
            not_run=counts["not_run"],
            running=counts["running"],
            business_status_counts=business,
            success_rate=None,
        )
        if self.summary.model_dump() != expected:
            raise ValueError("execution_summary_mismatch")
        if self.run_status == "completed" and counts["completed"] != len(self.rows):
            raise ValueError("completed_run_missing_cases")
        if self.run_status == "completed_with_errors" and (
            counts["running"]
            or counts["not_run"]
            or counts["interrupted"]
            or not (counts["error"] + counts["timeout"])
        ):
            raise ValueError("invalid_error_run_status")
        if self.run_status == "interrupted" and counts["running"]:
            raise ValueError("interrupted_run_still_running")
        return self
