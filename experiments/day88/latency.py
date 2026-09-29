"""Monotonic parent-side case timing; no provider latency or scoring claims."""

from math import ceil
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from experiments.day85.contracts import StrictContract, canonical_hash
from experiments.day87.execution_contracts import ExecutionReport, ExecutionRow

SCOPE = "parent_execute_case_including_startup_retries_cleanup_and_base_evidence"


def milliseconds(ns):
    return round(ns / 1_000_000, 3)


class LatencyMetrics(StrictContract):
    elapsed_ns: Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)] | None = None
    latency_ms: float | None = None
    clock: Literal["perf_counter_ns"] = "perf_counter_ns"
    scope: Literal[
        "parent_execute_case_including_startup_retries_cleanup_and_base_evidence"
    ] = SCOPE
    measurement: Literal["not_measured", "complete_case", "partial_case"] = (
        "not_measured"
    )
    input_tokens: None = None
    output_tokens: None = None
    cost: None = None
    notice: Literal["latency_only_no_usage_or_cost"] = "latency_only_no_usage_or_cost"

    @model_validator(mode="after")
    def coherent_clock(self) -> Self:
        if self.elapsed_ns is None:
            if self.latency_ms is not None or self.measurement != "not_measured":
                raise ValueError("unmeasured_latency_must_be_null")
        elif (
            self.latency_ms != milliseconds(self.elapsed_ns)
            or self.measurement == "not_measured"
        ):
            raise ValueError("duration_conversion_mismatch")
        return self


class TimedRow(ExecutionRow):
    metrics: LatencyMetrics = Field(default_factory=LatencyMetrics)

    @model_validator(mode="after")
    def match_execution(self) -> Self:
        measured = self.metrics.elapsed_ns is not None
        if self.execution_status in {"running", "not_run"} and measured:
            raise ValueError("unfinished_case_has_latency")
        if self.execution_status in {"completed", "error", "timeout"} and not measured:
            raise ValueError("terminal_case_missing_latency")
        if measured and self.metrics.measurement != (
            "complete_case" if self.execution_status == "completed" else "partial_case"
        ):
            raise ValueError("latency_outcome_mismatch")
        return self


def describe(values):
    """Nearest-rank p50/p95; null statistics for zero samples, never fabricate zero."""
    ordered = sorted(values)
    if not ordered:
        return dict(
            samples=0, min_ms=None, mean_ms=None, p50_ms=None, p95_ms=None, max_ms=None
        )
    return dict(
        samples=len(ordered),
        min_ms=milliseconds(ordered[0]),
        mean_ms=round(sum(ordered) / len(ordered) / 1_000_000, 3),
        p50_ms=milliseconds(ordered[ceil(len(ordered) * 0.50) - 1]),
        p95_ms=milliseconds(ordered[ceil(len(ordered) * 0.95) - 1]),
        max_ms=milliseconds(ordered[-1]),
    )


def aggregate(rows):
    values = [r.metrics.elapsed_ns for r in rows if r.metrics.elapsed_ns is not None]
    groups = {
        status: describe(
            [
                r.metrics.elapsed_ns
                for r in rows
                if r.execution_status == status and r.metrics.elapsed_ns is not None
            ]
        )
        for status in ("completed", "error", "timeout", "interrupted")
    }
    business = {
        status: describe(
            [
                r.metrics.elapsed_ns
                for r in rows
                if r.execution_status == "completed"
                and r.observed.business_status == status
            ]
        )
        for status in (
            "completed",
            "no_data",
            "needs_clarification",
            "failed",
            "rejected",
        )
    }
    return dict(
        scope=SCOPE,
        percentile_method="nearest_rank",
        measured_cases=len(values),
        unmeasured_cases=len(rows) - len(values),
        sum_case_elapsed_ms=milliseconds(sum(values)) if values else None,
        by_execution_status=groups,
        by_business_status=business,
        completed_includes_business_failure_and_rejection=True,
        partial_durations_are_not_time_to_success=True,
    )


class TimedReport(ExecutionReport):
    schema_version: Literal["day88-latency-v1"]
    rows: list[TimedRow]
    latency_summary: dict

    @model_validator(mode="after")
    def verify_aggregation(self) -> Self:
        if canonical_hash(self.latency_summary) != canonical_hash(aggregate(self.rows)):
            raise ValueError("latency_summary_mismatch")
        return self
