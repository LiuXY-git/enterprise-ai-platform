"""Strict, bounded planning output; a valid plan is not an executed task."""

import json
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]
StepId = Annotated[str, StringConstraints(pattern=r"^S[1-5]$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PlanStep(StrictModel):
    id: StepId
    action: Literal["retrieve", "analyze", "summarize"]
    description: Text
    expected_output: Text
    depends_on: list[StepId] = Field(max_length=4)


class PlanDecision(StrictModel):
    decision: Literal["plan", "clarify"]
    summary: Text
    steps: list[PlanStep] = Field(max_length=5)
    questions: list[Text] = Field(max_length=3)

    @model_validator(mode="after")
    def coherent_decision(self) -> Self:
        if self.decision == "clarify":
            if self.steps or not self.questions:
                raise ValueError("clarify requires questions and no steps")
            return self
        if not self.steps or self.questions:
            raise ValueError("plan requires steps and no questions")
        seen = set()
        for position, step in enumerate(self.steps, 1):
            if step.id != f"S{position}":
                raise ValueError("step IDs must be sequential")
            if len(set(step.depends_on)) != len(step.depends_on):
                raise ValueError("dependencies must be unique")
            if not set(step.depends_on) <= seen:
                raise ValueError("dependencies must reference earlier steps")
            seen.add(step.id)
        return self


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("non-standard JSON constant")


def parse_plan(raw: str) -> PlanDecision:
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 16000:
        raise ValueError("empty or oversized model output")
    value = json.loads(
        raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant
    )
    return PlanDecision.model_validate(value)
