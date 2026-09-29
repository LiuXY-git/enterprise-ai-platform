"""Bind fixture metering to observed execution; keep unavailable usage null."""

from typing import Literal, Self

from pydantic import model_validator

from experiments.day85.contracts import Sha256, StrictContract, canonical_hash
from experiments.day88.latency import TimedReport
from experiments.day89.usage import Pricing


def fixture_usage(execution):
    rows = []
    for case in execution.rows:
        observed = case.observed
        verified = (
            case.execution_status == "completed"
            and observed is not None
            and observed.model_requests == 0
        )
        rows.append(
            dict(
                case_id=case.case_id,
                status="fixture_no_provider_usage"
                if verified
                else "unknown_execution_usage",
                model_attempts=observed.model_attempts if observed else None,
                provider_requests=0 if verified else None,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                estimated_model_api_cost="0" if verified else None,
                token_source="not_applicable_fixture" if verified else "unavailable",
            )
        )
    known = sum(r["status"] == "fixture_no_provider_usage" for r in rows)
    return dict(
        rows=rows,
        summary=dict(
            selected=len(rows),
            fixture_cases=known,
            unknown_cases=len(rows) - known,
            provider_requests=0 if known == len(rows) else None,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            estimated_model_api_cost="0" if known == len(rows) else None,
            known_model_api_cost="0" if known else None,
            scope="model_api_only_excludes_local_compute_and_tools",
            notice="fixture_has_no_provider_usage_not_measured_zero_tokens",
        ),
    )


class MeteredReport(StrictContract):
    schema_version: Literal["day89-usage-v1"]
    report_kind: Literal["fixture_execution_with_explicit_usage_coverage"]
    execution: TimedReport
    execution_sha256: Sha256
    pricing: Pricing | None
    pricing_sha256: Sha256 | None
    usage: dict
    source_sha256_lf: dict[str, Sha256]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.execution_sha256 != canonical_hash(self.execution.model_dump()):
            raise ValueError("execution_snapshot_mismatch")
        expected = canonical_hash(self.pricing.model_dump()) if self.pricing else None
        if self.pricing_sha256 != expected:
            raise ValueError("pricing_snapshot_mismatch")
        if canonical_hash(self.usage) != canonical_hash(fixture_usage(self.execution)):
            raise ValueError("fixture_usage_mismatch")
        return self
