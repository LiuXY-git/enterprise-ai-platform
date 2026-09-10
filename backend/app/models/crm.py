from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

IDENTIFIER_PATTERN = r"^[A-Za-z0-9._:-]+$"

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=IDENTIFIER_PATTERN,
    ),
]
CompanyName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]
Industry = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]
Requirement = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=4000,
    ),
]
BudgetRange = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]
Summary = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=500,
    ),
]
Need = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]
NextAction = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=300,
    ),
]

Priority = Literal["high", "normal"]
ReviewStatus = Literal["not_required", "pending"]
NotificationMode = Literal["preview", "send"]
NotificationChannel = Literal["feishu", "wecom"]
NotificationStatus = Literal[
    "pending",
    "preview",
    "sent",
    "failed",
    "delivery_unknown",
    "skipped",
]
RiskFlag = Literal[
    "product_capability_unverified",
    "pricing_or_discount",
    "delivery_commitment",
    "prompt_injection",
    "sensitive_information",
]


class CRMModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        strict=True,
    )


class CRMCustomerUpsertRequest(CRMModel):
    customer_id: Identifier
    company_name: CompanyName
    industry: Industry | None = None
    sales_owner: Identifier


class CRMCustomerResponse(CRMCustomerUpsertRequest):
    created_at: datetime
    updated_at: datetime


class CRMFollowupAnalysis(CRMModel):
    summary: Summary
    needs: list[Need] = Field(min_length=1, max_length=5)
    missing_information: list[Need] = Field(max_length=5)
    next_actions: list[NextAction] = Field(min_length=1, max_length=5)
    risk_flags: list[RiskFlag] = Field(max_length=5)

    @field_validator("risk_flags")
    @classmethod
    def validate_unique_risk_flags(cls, value: list[RiskFlag]) -> list[RiskFlag]:
        if len(value) != len(set(value)):
            raise ValueError("risk_flags 不能包含重复值")
        return value


class CRMFollowupCreateRequest(CRMModel):
    customer: CRMCustomerUpsertRequest
    run_id: Identifier
    event_id: Identifier
    requirement_snapshot: Requirement
    analysis: CRMFollowupAnalysis
    priority: Priority
    review_status: ReviewStatus
    review_reasons: list[RiskFlag] = Field(max_length=5)
    notification_mode: NotificationMode = "preview"
    notification_channel: NotificationChannel = "feishu"

    @field_validator("review_reasons")
    @classmethod
    def validate_unique_review_reasons(
        cls,
        value: list[RiskFlag],
    ) -> list[RiskFlag]:
        if len(value) != len(set(value)):
            raise ValueError("review_reasons 不能包含重复值")
        return value

    @model_validator(mode="after")
    def validate_review_state(self) -> "CRMFollowupCreateRequest":
        if self.review_status == "pending" and not self.review_reasons:
            raise ValueError("pending 状态必须提供 review_reasons")

        if self.review_status == "not_required" and self.review_reasons:
            raise ValueError("not_required 状态不能提供 review_reasons")

        if set(self.review_reasons) != set(self.analysis.risk_flags):
            raise ValueError("review_reasons 必须与 analysis.risk_flags 一致")

        return self


class CRMFollowupResponse(CRMModel):
    followup_id: Identifier
    customer_id: Identifier
    run_id: Identifier
    event_id: Identifier
    requirement_snapshot: Requirement
    analysis: CRMFollowupAnalysis
    priority: Priority
    review_status: ReviewStatus
    review_reasons: list[RiskFlag] = Field(max_length=5)
    notification_mode: NotificationMode
    notification_channel: NotificationChannel | None
    notification_status: NotificationStatus
    notification_request_key: Identifier | None
    notification_message_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
    )
    notification_error_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_:-]*$",
    )
    created_at: datetime
    updated_at: datetime


class CRMFollowupCreateResponse(CRMFollowupResponse):
    created: bool


class CRMFollowupListResponse(CRMModel):
    customer_id: Identifier
    count: int = Field(ge=0)
    followups: list[CRMFollowupResponse]
