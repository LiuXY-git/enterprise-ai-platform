from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WorkflowRunStatus = Literal[
    "running",
    "succeeded",
    "failed",
    "needs_human_review",
]

WorkflowRunFinalStatus = Literal[
    "succeeded",
    "needs_human_review",
]


class WorkflowRunStartRequest(BaseModel):
    event_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    workflow_name: str = Field(
        min_length=1,
        max_length=128,
    )
    source: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    requester: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    report_date: date
    input_data: dict[str, Any]
    n8n_execution_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    replay: bool = False


class WorkflowRunStartResponse(BaseModel):
    run_id: str
    status: WorkflowRunStatus
    should_process: bool
    duplicate: bool
    replayed: bool
    retry_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    input_data: dict[str, Any]


class WorkflowRunFinishRequest(BaseModel):
    status: WorkflowRunFinalStatus
    output_data: dict[str, Any]
    category: str | None = Field(
        default=None,
        max_length=64,
    )
    priority: str | None = Field(
        default=None,
        max_length=32,
    )
    elapsed_time: float | None = Field(
        default=None,
        ge=0,
    )
    total_tokens: int | None = Field(
        default=None,
        ge=0,
    )


class WorkflowRunFailureRequest(BaseModel):
    error_type: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_:-]*$",
    )
    error_message: str = Field(
        min_length=1,
        max_length=1000,
    )


class WorkflowRunResponse(BaseModel):
    run_id: str
    event_id: str
    workflow_name: str
    source: str
    requester: str
    report_date: date
    status: WorkflowRunStatus
    category: str | None
    priority: str | None
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error_type: str | None
    error_message: str | None
    n8n_execution_id: str | None
    retry_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    elapsed_time: float | None
    total_tokens: int | None
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowRunListResponse(BaseModel):
    report_date: date
    count: int = Field(ge=0)
    runs: list[WorkflowRunResponse]
