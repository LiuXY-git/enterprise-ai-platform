"""Bounded smoke, fixed fixture sales and explicit local decision contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

JobStatus = Literal["queued", "running", "succeeded", "failed", "interrupted"]


class SmokeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=200)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["smoke"] = "smoke"
    mode: Literal["fixture"] = "fixture"
    input: SmokeInput


SalesCase = Literal["monthly", "customer", "empty", "clarification"]


class SalesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case: SalesCase


class SalesRequest(SalesInput):
    mode: Literal["fixture"] = "fixture"


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: Literal["approve", "reject"]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)
    confirm: Literal["APPROVE", "REJECT"]
    reason: Literal["not_needed", "needs_revision"] = "not_needed"

    @model_validator(mode="after")
    def explicit_action(self):
        if self.confirm.lower() != self.decision:
            raise ValueError("confirmation_mismatch")
        return self


class SalesResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case: SalesCase
    mode: Literal["fixture"]
    business_status: Literal["completed", "no_data", "needs_clarification"]
    answer: str = Field(min_length=1, max_length=6000)
    source_ids: dict[str, str]
    report: dict | None
    receipt: dict | None
    events: list[dict]
    model_requests: Literal[0]
    external_send: Literal[False]

    @model_validator(mode="after")
    def consistent_sources(self):
        import re

        required = {"task_id", "run_id"}
        if self.business_status != "needs_clarification":
            required.add("approval_id")
        if set(self.source_ids) != required or not all(
            re.fullmatch(r"[0-9a-f]{32}", value) for value in self.source_ids.values()
        ):
            raise ValueError("invalid_source_ids")
        if self.business_status == "needs_clarification":
            if (
                self.report is not None
                or self.receipt is not None
                or self.case != "clarification"
            ):
                raise ValueError("invalid_clarification")
        elif (
            not self.report
            or not self.receipt
            or (
                self.receipt.get("receipt_id") != self.source_ids["run_id"] + "/T1"
                or self.report.get("citation") != self.receipt["receipt_id"]
                or self.report.get("status") != self.business_status
                or self.report.get("fictional") is not True
            )
        ):
            raise ValueError("invalid_report_source")
        return self


class JobError(BaseModel):
    code: Literal[
        "worker_interrupted",
        "worker_lease_expired",
        "task_timeout",
        "task_failed",
        "invalid_task_result",
    ]
    message: str


class JobView(BaseModel):
    job_id: str
    kind: Literal["smoke", "agent"]
    mode: Literal["fixture"]
    status: JobStatus
    stage: str
    input: SmokeInput | SalesInput
    result: dict | None
    error: JobError | None
    source_ids: dict
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None


class Submission(BaseModel):
    job: JobView
    reused: bool


class JobList(BaseModel):
    jobs: list[JobView]
    total: int
    limit: int
    offset: int


class WorkerView(BaseModel):
    status: Literal["missing", "healthy", "stale", "stopped"]
    heartbeat_at: str | None
    lease_expires_at: str | None
