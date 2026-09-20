"""Day 61 sales scenario contracts; local snapshots only, no CRM or model calls."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[
    str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
]
Text = Annotated[str, StringConstraints(min_length=1, max_length=300)]
Day = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Risk = Literal[
    "product_capability_unverified",
    "pricing_or_discount",
    "delivery_commitment",
    "prompt_injection",
    "sensitive_information",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class SalesRequest(Contract):
    objective: Literal["prioritize_followups"] = "prioritize_followups"
    period_start: Day | None = None
    period_end: Day | None = None
    customer_ids: list[Identifier] | None = Field(
        default=None, min_length=1, max_length=20
    )
    timezone: Literal["+08:00"] = "+08:00"

    @field_validator("period_start", "period_end")
    @classmethod
    def valid_day(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def valid_scope(self):
        if self.customer_ids and len(self.customer_ids) != len(set(self.customer_ids)):
            raise ValueError("duplicate_customer_id")
        if self.period_start and self.period_end:
            days = (
                date.fromisoformat(self.period_end)
                - date.fromisoformat(self.period_start)
            ).days
            if not 0 <= days <= 30:
                raise ValueError("period_must_cover_1_to_31_days")
        return self

    def missing_fields(self) -> list[str]:
        return [
            name
            for name in ("period_start", "period_end", "customer_ids")
            if getattr(self, name) is None
        ]


class FollowupEvidence(Contract):
    # A projection of existing CRM fields, not a new API response model.
    followup_id: Identifier
    customer_id: Identifier
    created_at: Annotated[
        str,
        StringConstraints(
            pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$"
        ),
    ]
    priority: Literal["high", "normal"]
    review_status: Literal["not_required", "pending"]
    risk_flags: list[Risk] = Field(max_length=5)
    missing_information: list[Text] = Field(max_length=5)
    summary: Annotated[str, StringConstraints(min_length=1, max_length=500)]

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value):
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError("timestamp_requires_timezone")
        return value

    @model_validator(mode="after")
    def coherent_review(self):
        if len(self.risk_flags) != len(set(self.risk_flags)):
            raise ValueError("duplicate_risk_flag")
        if bool(self.risk_flags) != (self.review_status == "pending"):
            raise ValueError("review_status_must_match_risks")
        return self


class CustomerSnapshot(Contract):
    customer_id: Identifier
    fetch_status: Literal["ok", "not_found", "error"]
    records: list[FollowupEvidence] = Field(max_length=50)
    error_code: Literal["timeout", "unavailable"] | None = None

    @model_validator(mode="after")
    def coherent_fetch(self):
        if (self.fetch_status == "error") != (self.error_code is not None):
            raise ValueError("fetch_status_must_match_error")
        if self.fetch_status != "ok" and self.records:
            raise ValueError("failed_fetch_cannot_contain_records")
        if any(record.customer_id != self.customer_id for record in self.records):
            raise ValueError("record_customer_mismatch")
        return self


class ScenarioInput(Contract):
    data_source: Literal["fictional_fixture"]
    request: SalesRequest
    snapshots: list[CustomerSnapshot] = Field(max_length=20)

    @model_validator(mode="after")
    def coherent_snapshot(self):
        ids = [item.customer_id for item in self.snapshots]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_snapshot")
        followup_ids = [r.followup_id for s in self.snapshots for r in s.records]
        if len(followup_ids) != len(set(followup_ids)):
            raise ValueError("duplicate_followup_id")
        if self.request.missing_fields():
            if self.snapshots:
                raise ValueError("clarify_request_before_fetching")
        elif set(ids) != set(self.request.customer_ids):
            raise ValueError("snapshot_must_cover_exact_requested_customers")
        return self


class Recommendation(Contract):
    customer_id: Identifier
    category: Literal[
        "manual_review", "needs_information", "priority_followup", "routine_followup"
    ]
    reason_code: Literal[
        "review_pending",
        "missing_information",
        "latest_priority_high",
        "latest_priority_normal",
    ]
    suggested_action: Literal[
        "review_risks",
        "collect_missing_information",
        "prepare_followup",
        "maintain_followup",
    ]
    evidence_ids: list[Identifier] = Field(min_length=1, max_length=50)
    missing_information: list[Text] = Field(max_length=250)
    risk_flags: list[Risk] = Field(max_length=5)


class Gap(Contract):
    customer_id: Identifier
    reason: Literal[
        "source_error",
        "not_found",
        "no_records",
        "conflicting_priority",
        "review_required",
        "missing_information",
    ]
    evidence_ids: list[Identifier] = Field(max_length=50)


class SalesReport(Contract):
    contract_version: Literal["0.1.0"] = "0.1.0"
    execution_mode: Literal["contract_simulation"] = "contract_simulation"
    model_requests: Literal[0] = 0
    business_actions_executed: Literal[False] = False
    scope: SalesRequest
    status: Literal["waiting_for_input", "completed", "no_data", "incomplete", "failed"]
    missing_fields: list[Literal["period_start", "period_end", "customer_ids"]] = Field(
        max_length=3
    )
    recommendations: list[Recommendation] = Field(max_length=20)
    gaps: list[Gap] = Field(max_length=40)
