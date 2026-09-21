"""Model-facing decision only; execution metadata always belongs to the host."""

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day61"))
from sales_contract import (  # noqa: E402
    Contract,
    Gap,
    Recommendation,
    SalesReport,
    SalesRequest,
    ScenarioInput,
)
from scenario_rules import validate_report  # noqa: E402

MAX_OUTPUT_CHARS = 32000


class ReportDecision(Contract):
    scope: SalesRequest
    status: Literal["waiting_for_input", "completed", "no_data", "incomplete", "failed"]
    missing_fields: list[Literal["period_start", "period_end", "customer_ids"]] = Field(
        max_length=3
    )
    recommendations: list[Recommendation] = Field(max_length=20)
    gaps: list[Gap] = Field(max_length=40)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("non_standard_json_constant")


def parse_decision(raw: str) -> ReportDecision:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_OUTPUT_CHARS:
        raise ValueError("empty_or_oversized_output")
    value = json.loads(
        raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
    return ReportDecision.model_validate(value)


def verify_decision(source: ScenarioInput, decision: ReportDecision) -> None:
    # Reuse Day 61's evidence oracle; its simulation metadata is not model output.
    validate_report(source, SalesReport(**decision.model_dump()))
