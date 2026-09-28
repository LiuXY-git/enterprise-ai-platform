"""Design-stage evaluation contracts. No runner or success-rate calculator."""

import hashlib
import json
import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1-design"
SOURCE_FILES = {
    "experiments/day82/prompt_lab.py",
    "experiments/day82/prompt_policy.py",
    "experiments/day82/candidate.md",
    "agent-center/release-v1.0.0.json",
}
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Count = Annotated[int, Field(ge=0, strict=True)]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def canonical_hash(value):
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AgentSpec(StrictContract):
    schema_version: Literal["0.1-design"]
    agent_id: Identifier
    adapter_id: Literal["day82_prepare_fixture"]
    mode: Literal["fixture"]
    declared_source_commit: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    source_sha256_lf: dict[str, Sha256]

    @model_validator(mode="after")
    def source_scope(self) -> Self:
        if set(self.source_sha256_lf) != SOURCE_FILES:
            raise ValueError("source_inventory_mismatch")
        return self


class CaseInput(StrictContract):
    case: Literal["monthly", "customer", "empty", "clarification"]
    scenario: Literal[
        "normal",
        "tool_timeout_once",
        "tool_timeout_always",
        "model_timeout_once",
        "report_timeout",
        "invalid_report",
        "invalid_arguments",
    ]

    @model_validator(mode="after")
    def supported_combination(self) -> Self:
        if self.case == "clarification" and self.scenario != "normal":
            raise ValueError("clarification_only_supports_normal_design_case")
        return self


class Criterion(StrictContract):
    criterion_id: Identifier
    field: Literal[
        "total_yuan",
        "order_count",
        "customer_id",
        "has_citation",
        "approval_status",
        "simulated_effects",
        "external_send",
    ]
    operator: Literal["eq"]
    expected: str | int | bool | None

    @model_validator(mode="after")
    def typed_expected(self) -> Self:
        value = self.expected
        if self.field == "total_yuan":
            valid = isinstance(value, str) and re.fullmatch(
                r"(?:0|[1-9][0-9]*)\.[0-9]{2}", value
            )
        elif self.field in {"order_count", "simulated_effects"}:
            valid = type(value) is int and value >= 0
        elif self.field in {"has_citation", "external_send"}:
            valid = type(value) is bool
        elif self.field == "customer_id":
            valid = value is None or (
                isinstance(value, str) and re.fullmatch(r"C[0-9]{3}", value)
            )
        else:
            valid = value in (None, "pending") and (value is None or type(value) is str)
        if not valid:
            raise ValueError("criterion_value_type_mismatch")
        # This adapter only prepares approval; it can never deliver a message.
        if (self.field == "external_send" and value is not False) or (
            self.field == "simulated_effects" and value != 0
        ):
            raise ValueError("prepare_adapter_has_no_delivery")
        return self


class Expectation(StrictContract):
    business_status: Literal[
        "completed", "no_data", "needs_clarification", "failed", "rejected"
    ]
    criteria: Annotated[list[Criterion], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def unambiguous_rules(self) -> Self:
        ids = [r.criterion_id for r in self.criteria]
        fields = [r.field for r in self.criteria]
        if len(set(ids)) != len(ids) or len(set(fields)) != len(fields):
            raise ValueError("duplicate_or_conflicting_criteria")
        return self


class TestCase(StrictContract):
    case_id: Identifier
    task: Annotated[str, Field(min_length=1, max_length=1000)]
    input: CaseInput
    expected: Expectation

    @model_validator(mode="after")
    def nonempty_task(self) -> Self:
        if not self.task.strip():
            raise ValueError("empty_task")
        return self


class Dataset(StrictContract):
    schema_version: Literal["0.1-design"]
    dataset_id: Identifier
    dataset_version: Literal["0.1-design"]
    purpose: Literal["contract_smoke_only"]
    data_kind: Literal["fictional"]
    adapter_id: Literal["day82_prepare_fixture"]
    cases: Annotated[list[TestCase], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique_case_ids(self) -> Self:
        ids = [c.case_id for c in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate_case_ids")
        return self


class UnmeasuredMetrics(StrictContract):
    latency_ms: None = None
    input_tokens: None = None
    output_tokens: None = None
    cost: None = None
    notice: Literal["not_run_not_measured"] = "not_run_not_measured"


class PlannedResult(StrictContract):
    case_id: Identifier
    execution_status: Literal["not_run"] = "not_run"
    judgement: Literal["not_evaluated"] = "not_evaluated"
    observed_business_status: None = None
    error: None = None
    metrics: UnmeasuredMetrics = Field(default_factory=UnmeasuredMetrics)


class PlanSummary(StrictContract):
    total_cases: Count
    not_run: Count
    passed: Count = 0
    failed: Count = 0
    errors: Count = 0
    success_rate: None = None


class EvaluationPlan(StrictContract):
    schema_version: Literal["0.1-design"]
    report_kind: Literal["preflight_plan_not_evaluation"]
    execution_status: Literal["not_run"]
    agent: AgentSpec
    dataset: Dataset
    agent_spec_sha256: Sha256
    dataset_sha256: Sha256
    identity_check: Literal["declared_local_files_only_commit_not_resolved"]
    rows: list[PlannedResult]
    summary: PlanSummary

    @model_validator(mode="after")
    def consistent_plan(self) -> Self:
        if self.agent.adapter_id != self.dataset.adapter_id:
            raise ValueError("adapter_mismatch")
        if self.agent_spec_sha256 != canonical_hash(
            self.agent.model_dump()
        ) or self.dataset_sha256 != canonical_hash(self.dataset.model_dump()):
            raise ValueError("descriptor_hash_mismatch")
        if [r.case_id for r in self.rows] != [c.case_id for c in self.dataset.cases]:
            raise ValueError("plan_case_coverage_mismatch")
        summary = self.summary
        if (
            summary.total_cases != len(self.rows)
            or summary.not_run != len(self.rows)
            or any((summary.passed, summary.failed, summary.errors))
        ):
            raise ValueError("unrun_plan_cannot_claim_results")
        return self
