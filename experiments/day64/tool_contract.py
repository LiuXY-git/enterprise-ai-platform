"""One allowlisted, deterministic teaching tool. No business I/O or eval."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_ARGUMENT_CHARS = 2048


class ToolInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OrderArguments(Contract):
    unit_price_cents: int = Field(
        ge=0, le=1_000_000_000, description="单价，人民币分；199元填写19900"
    )
    quantity: int = Field(ge=1, le=1000, description="数量，整数")
    discount_percent: int = Field(
        ge=0, le=100, description="减免百分比；0表示不打折，10表示九折"
    )


class FunctionCall(Contract):
    name: Literal["calculate_order_total"]
    arguments: str = Field(min_length=1, max_length=MAX_ARGUMENT_CHARS)


class ToolCall(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    type: Literal["function"]
    function: FunctionCall


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError("non_standard_json_constant")


def validate_call(call: dict) -> tuple[ToolCall, OrderArguments]:
    try:
        request = ToolCall.model_validate(call)
    except (ValueError, TypeError, RecursionError):
        raise ToolInputError("invalid_tool_call") from None
    try:
        arguments = json.loads(
            request.function.arguments,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
        return request, OrderArguments.model_validate(arguments)
    except (ValueError, TypeError, RecursionError):
        raise ToolInputError("invalid_tool_arguments") from None


def calculate_order_total(args: OrderArguments) -> dict:
    """All money is integer cents; ties are rounded up to one cent."""
    subtotal = args.unit_price_cents * args.quantity
    total = (subtotal * (100 - args.discount_percent) + 50) // 100
    return {
        "currency": "CNY",
        "subtotal_cents": subtotal,
        "discount_percent": args.discount_percent,
        "total_cents": total,
        "total_yuan": f"{total // 100}.{total % 100:02d}",
    }


def execute_call(call: dict) -> dict:
    _, arguments = validate_call(call)
    return calculate_order_total(arguments)


def tool_definitions() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "calculate_order_total",
                "description": "计算虚构订单优惠后的金额，只做算术，不创建或支付订单。",
                "parameters": OrderArguments.model_json_schema(),
            },
        }
    ]
