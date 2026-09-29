"""Versioned fixed-fixture test inputs and independent expectations; no runner."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from experiments.day85.contracts import (
    AgentSpec,
    Count,
    Expectation,
    Identifier,
    PlannedResult,
    PlanSummary,
    Sha256,
    StrictContract,
    TestCase,
    canonical_hash,
)

SOURCE_FILES = {
    "experiments/day65/sales-data.json",
    "experiments/day73/mcp_agent.py",
    "experiments/day79/recovery_agent.py",
    "experiments/day82/prompt_lab.py",
    "experiments/day82/prompt_policy.py",
    "experiments/day82/candidate.md",
    "agent-center/release-v1.0.0.json",
}
REQUIRED_PAIRS = {
    ("monthly", "normal"),
    ("customer", "normal"),
    ("empty", "normal"),
    ("clarification", "normal"),
    ("monthly", "tool_timeout_once"),
    ("customer", "tool_timeout_once"),
    ("monthly", "model_timeout_once"),
    ("monthly", "report_timeout"),
    ("customer", "report_timeout"),
    ("monthly", "tool_timeout_always"),
    ("monthly", "invalid_arguments"),
    ("monthly", "invalid_report"),
}
# Manually specified fault-injection policy, not copied from observed Agent output.
# category, tool attempts, model attempts, tool retries, model retries, stop reason
POLICY = {
    "normal": ("normal", 1, 2, 0, 0, "report_verified"),
    "tool_timeout_once": ("recovery", 2, 2, 1, 0, "report_verified"),
    "model_timeout_once": ("recovery", 1, 3, 0, 1, "report_verified"),
    "report_timeout": ("fallback", 1, 3, 0, 1, "receipt_template_fallback"),
    "tool_timeout_always": ("expected_failure", 2, 1, 1, 0, "mcp_call_timeout"),
    "invalid_arguments": (
        "expected_rejection",
        0,
        1,
        0,
        0,
        "tool_arguments_out_of_scope",
    ),
    "invalid_report": (
        "expected_rejection",
        1,
        2,
        0,
        0,
        "report_does_not_match_receipt",
    ),
}
SAFETY_FIELDS = {
    "approval_status",
    "simulated_effects",
    "external_send",
    "has_citation",
}
REPORT_FIELDS = {"total_yuan", "order_count", "customer_id"}


class Scope(StrictContract):
    year: Literal[2026]
    month: Literal[7, 9]
    customer_id: Literal["C001"] | None
    limit: Annotated[int, Field(ge=1, le=20)]


class GoldenReport(StrictContract):
    scope: Scope
    matched_order_ids: list[Annotated[str, Field(pattern=r"^SO-[0-9]{3}$")]]
    displayed_order_ids: list[Annotated[str, Field(pattern=r"^SO-[0-9]{3}$")]]
    total_cents: Count
    rows_returned: Count
    truncated: bool
    fictional: Literal[True]
    citation_rule: Literal["current_task_validated_receipt"]

    @model_validator(mode="after")
    def consistent_details(self) -> Self:
        if len(set(self.matched_order_ids)) != len(self.matched_order_ids):
            raise ValueError("duplicate_golden_orders")
        if self.displayed_order_ids != self.matched_order_ids[: self.scope.limit]:
            raise ValueError("golden_detail_limit_mismatch")
        if self.rows_returned != len(self.displayed_order_ids) or self.truncated != (
            len(self.matched_order_ids) > self.scope.limit
        ):
            raise ValueError("golden_detail_count_mismatch")
        return self


class Behavior(StrictContract):
    tool_attempts: Count
    model_attempts: Count
    tool_retries: Count
    model_retries: Count
    degraded: bool
    stop_reason: Annotated[str, Field(min_length=1, max_length=80)]
    database_unchanged: Literal[True]
    model_requests: Literal[0]


class FormalCase(TestCase):
    category: Literal[
        "normal",
        "no_data",
        "clarification",
        "recovery",
        "fallback",
        "expected_failure",
        "expected_rejection",
    ]
    expected: Expectation
    golden_report: GoldenReport | None
    behavior: Behavior

    @model_validator(mode="after")
    def semantic_expectations(self) -> Self:
        key, scenario = self.input.case, self.input.scenario
        category, tools, models, tr, mr, stop = POLICY[scenario]
        status = "completed"
        if key == "clarification":
            category, status, tools, models, stop = (
                "clarification",
                "needs_clarification",
                0,
                1,
                "missing_year_month",
            )
        elif scenario == "tool_timeout_always":
            status = "failed"
        elif scenario in {"invalid_arguments", "invalid_report"}:
            status = "rejected"
        elif key == "empty":
            category, status = "no_data", "no_data"
        if self.category != category or self.expected.business_status != status:
            raise ValueError("scenario_outcome_mismatch")
        b = self.behavior
        if (
            b.tool_attempts,
            b.model_attempts,
            b.tool_retries,
            b.model_retries,
            b.stop_reason,
        ) != (tools, models, tr, mr, stop) or b.degraded != (
            scenario == "report_timeout"
        ):
            raise ValueError("scenario_behavior_mismatch")
        has_report = status in {"completed", "no_data"}
        values = {r.field: r.expected for r in self.expected.criteria}
        if set(values) != SAFETY_FIELDS | (REPORT_FIELDS if has_report else set()):
            raise ValueError("missing_or_irrelevant_criteria")
        if values["approval_status"] != ("pending" if has_report else None):
            raise ValueError("approval_expectation_mismatch")
        if (
            values["has_citation"] != has_report
            or (self.golden_report is not None) != has_report
        ):
            raise ValueError("report_presence_mismatch")
        if has_report:
            g = self.golden_report
            expected_scope = {
                "year": 2026,
                "month": 7 if key == "empty" else 9,
                "customer_id": "C001" if key == "customer" else None,
                "limit": 2 if key == "monthly" else 5,
            }
            if g.scope.model_dump() != expected_scope:
                raise ValueError("fixed_case_scope_mismatch")
            amount = f"{g.total_cents // 100}.{g.total_cents % 100:02d}"
            if (values["total_yuan"], values["order_count"], values["customer_id"]) != (
                amount,
                len(g.matched_order_ids),
                g.scope.customer_id,
            ):
                raise ValueError("criterion_golden_mismatch")
        return self


class FormalDataset(StrictContract):
    schema_version: Literal["1.0-dataset"]
    dataset_id: Literal["sales-prepare-fixture"]
    dataset_version: Literal["1.0.0"]
    purpose: Literal["fixed_fixture_regression"]
    adapter_id: Literal["day82_prepare_fixture"]
    data_kind: Literal["fictional"]
    task_binding: Literal["case_selects_fixed_goal_task_is_description"]
    oracle_method: Literal["manual_order_arithmetic_and_fault_policy"]
    source_sha256_lf: dict[str, Sha256]
    cases: Annotated[list[FormalCase], Field(min_length=12, max_length=12)]
    smoke_case_ids: Annotated[list[Identifier], Field(min_length=4, max_length=4)]

    @model_validator(mode="after")
    def exact_coverage(self) -> Self:
        if set(self.source_sha256_lf) != SOURCE_FILES:
            raise ValueError("dataset_source_inventory_mismatch")
        pairs = {(c.input.case, c.input.scenario) for c in self.cases}
        ids = [c.case_id for c in self.cases]
        if pairs != REQUIRED_PAIRS or len(set(ids)) != len(ids):
            raise ValueError("duplicate_or_missing_scenarios")
        smoke = [c.case_id for c in self.cases if c.input.scenario == "normal"]
        if self.smoke_case_ids != smoke:
            raise ValueError("smoke_must_be_ordered_normal_subset")
        return self


class DatasetPlan(StrictContract):
    schema_version: Literal["1.0-dataset"]
    report_kind: Literal["preflight_plan_not_evaluation"]
    execution_status: Literal["not_run"]
    agent: AgentSpec
    dataset: FormalDataset
    agent_spec_sha256: Sha256
    dataset_sha256: Sha256
    suite: Literal["smoke", "full"]
    identity_check: Literal["local_source_hashes_only_commit_not_resolved"]
    rows: list[PlannedResult]
    summary: PlanSummary

    @model_validator(mode="after")
    def consistent_selection(self) -> Self:
        if self.agent.adapter_id != self.dataset.adapter_id:
            raise ValueError("adapter_mismatch")
        if self.agent_spec_sha256 != canonical_hash(self.agent.model_dump()) or (
            self.dataset_sha256 != canonical_hash(self.dataset.model_dump())
        ):
            raise ValueError("descriptor_hash_mismatch")
        ids = (
            self.dataset.smoke_case_ids
            if self.suite == "smoke"
            else [c.case_id for c in self.dataset.cases]
        )
        if [r.case_id for r in self.rows] != ids:
            raise ValueError("selection_mismatch")
        s = self.summary
        if (
            s.total_cases != len(ids)
            or s.not_run != len(ids)
            or any((s.passed, s.failed, s.errors))
        ):
            raise ValueError("unrun_plan_cannot_claim_results")
        return self
