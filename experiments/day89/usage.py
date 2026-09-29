"""Explicit usage coverage and decimal estimates, never infer tokens from text."""

from decimal import Decimal, localcontext
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from experiments.day85.contracts import StrictContract

Tokens = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
Label = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,99}$")]
Rate = Annotated[str, Field(pattern=r"^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,8})?$")]


class Pricing(StrictContract):
    schema_version: Literal["day89-pricing-v1"]
    price_id: Label
    provider: Label
    model: Label
    currency: Literal["CNY", "USD"]
    input_per_million: Rate
    output_per_million: Rate
    basis: Literal["user_supplied_flat_text_rates"]
    effective_date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    source_note: Annotated[str, Field(min_length=1, max_length=300)]
    illustrative: bool

    @model_validator(mode="after")
    def valid_date(self) -> Self:
        from datetime import date

        date.fromisoformat(self.effective_date)
        return self


class Attempt(StrictContract):
    attempt_id: Annotated[int, Field(strict=True, ge=1)]
    provider: Label
    model: Label
    origin: Literal["provider_response", "synthetic_response"]
    outcome: Literal["response", "transport_error", "incomplete_response"]
    http_status: Annotated[int, Field(strict=True, ge=100, le=599)] | None
    usage_status: Literal["reported", "missing", "invalid"]
    input_tokens: Tokens | None
    output_tokens: Tokens | None
    total_tokens: Tokens | None
    flat_pricing_supported: bool

    @model_validator(mode="after")
    def consistent_usage(self) -> Self:
        values = (self.input_tokens, self.output_tokens, self.total_tokens)
        if self.usage_status == "reported":
            if (
                any(v is None for v in values)
                or self.total_tokens != self.input_tokens + self.output_tokens
            ):
                raise ValueError("invalid_reported_usage")
            if self.outcome != "response":
                raise ValueError("incomplete_response_cannot_report_usage")
        elif any(v is not None for v in values) or self.flat_pricing_supported:
            raise ValueError("missing_usage_cannot_claim_tokens_or_pricing")
        if self.outcome == "transport_error" and self.http_status is not None:
            raise ValueError("transport_error_has_http_status")
        return self


def parse_usage(payload):
    result = dict(
        usage_status="missing",
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        flat_pricing_supported=False,
    )
    if not isinstance(payload, dict) or payload.get("usage") is None:
        return result
    usage = payload["usage"]
    fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    if not isinstance(usage, dict) or any(
        type(usage.get(k)) is not int or not 0 <= usage[k] <= 1_000_000_000
        for k in fields
    ):
        return {**result, "usage_status": "invalid"}
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        return {**result, "usage_status": "invalid"}
    # Nonzero cache/reasoning/audio details and unknown billing fields need a
    # richer price model. Keep token counts but do not guess their cost.
    flat = True
    for key, value in usage.items():
        if key in fields:
            continue
        if key not in {
            "prompt_tokens_details",
            "completion_tokens_details",
        } or not isinstance(value, dict):
            flat = False
        elif any(type(v) is not int or v != 0 for v in value.values()):
            flat = False
    return dict(
        usage_status="reported",
        input_tokens=usage["prompt_tokens"],
        output_tokens=usage["completion_tokens"],
        total_tokens=usage["total_tokens"],
        flat_pricing_supported=flat,
    )


def estimate(attempt, price):
    if attempt.usage_status != "reported":
        return None, "usage_unavailable"
    if price is None:
        return None, "price_missing"
    if (attempt.provider, attempt.model) != (price.provider, price.model):
        return None, "price_identity_mismatch"
    if not attempt.flat_pricing_supported:
        return None, "unsupported_billing_details"
    with localcontext() as context:
        context.prec = 40
        cost = (
            Decimal(attempt.input_tokens) * Decimal(price.input_per_million)
            + Decimal(attempt.output_tokens) * Decimal(price.output_per_million)
        ) / Decimal(1_000_000)
    return cost, "estimated"


def money(value):
    # Exact finite decimals: rates have <=8 decimal places, tokens are integers.
    return format(value, "f")


def summarize(attempts, price=None):
    if len(attempts) > 128:
        raise ValueError("attempt_ledger_limit_exceeded")
    if len({a.attempt_id for a in attempts}) != len(attempts) or [
        a.attempt_id for a in attempts
    ] != list(range(1, len(attempts) + 1)):
        raise ValueError("attempt_ledger_must_be_unique_ordered_and_contiguous")
    if len({a.origin for a in attempts}) > 1:
        raise ValueError("synthetic_and_provider_usage_must_not_be_mixed")
    reported = [a for a in attempts if a.usage_status == "reported"]
    complete = bool(attempts) and len(reported) == len(attempts)
    estimates = [estimate(a, price) for a in attempts]
    priced = [cost for cost, reason in estimates if cost is not None]
    cost_complete = bool(attempts) and len(priced) == len(attempts)
    return dict(
        attempts=len(attempts),
        reported_attempts=len(reported),
        missing_or_invalid_attempts=len(attempts) - len(reported),
        coverage="complete" if complete else "partial" if reported else "unknown",
        origin=attempts[0].origin if attempts else None,
        input_tokens=sum(a.input_tokens for a in reported) if complete else None,
        output_tokens=sum(a.output_tokens for a in reported) if complete else None,
        total_tokens=sum(a.total_tokens for a in reported) if complete else None,
        known_input_tokens=sum(a.input_tokens for a in reported) if reported else None,
        known_output_tokens=sum(a.output_tokens for a in reported)
        if reported
        else None,
        estimated_cost=money(sum(priced, Decimal(0))) if cost_complete else None,
        known_estimated_cost=money(sum(priced, Decimal(0))) if priced else None,
        cost_coverage="complete"
        if cost_complete
        else "partial"
        if priced
        else "unknown",
        currency=price.currency if price else None,
        cost_reasons=[reason for cost, reason in estimates],
        illustrative=price.illustrative if price else None,
        notice="reported_usage_with_configured_estimate_not_provider_invoice",
    )
