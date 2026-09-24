"""Validate discovered MCP contracts and receipts before exposing them to a model."""

import copy
import json
import sys
from pathlib import Path
from typing import Literal

import anyio
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
for day in (65, 72):
    sys.path.insert(0, str(ROOT / f"experiments/day{day}"))
from sales_mcp_server import OUTPUT_SCHEMA, SAFE_ERRORS, TOOL_NAME  # noqa: E402
from sales_sql import Order, SalesQuery, reject_constant, unique_object  # noqa: E402


class BridgeError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Period(StrictModel):
    start: str
    end_exclusive: str


class SalesReceipt(StrictModel):
    source: Literal["day65-fictional-sales"]
    query_id: Literal["monthly_paid_sales_v1"]
    period: Period
    customer_id: str | None
    order_status: Literal["paid"]
    currency: Literal["CNY"]
    data_status: Literal["ok", "no_data"]
    order_count: int = Field(ge=0, le=100_000)
    total_cents: int = Field(ge=0, le=100_000_000_000_000)
    total_yuan: str
    orders: list[Order] = Field(max_length=20)
    rows_returned: int = Field(ge=0, le=20)
    truncated: bool
    read_only: bool


def parse_json(text):
    return json.loads(
        text, object_pairs_hook=unique_object, parse_constant=reject_constant
    )


def validate_receipt(reply, parameters):
    """Check association and consistency, not the truth of the underlying business."""
    try:
        if len(reply.content) != 1 or reply.content[0].type != "text":
            raise ValueError
        text = reply.content[0].text
        body = reply.structured_content
        if (
            len(text) > 12000
            or len(json.dumps(body, ensure_ascii=False, allow_nan=False)) > 12000
        ):
            raise ValueError
        if (
            json.dumps(parse_json(text), sort_keys=True, allow_nan=False)
            != json.dumps(body, sort_keys=True, allow_nan=False)
            or not isinstance(body, dict)
            or body.get("fictional") is not True
        ):
            raise ValueError
        if reply.is_error:
            if (
                set(body) != {"status", "fictional", "error"}
                or body["status"] != "error"
            ):
                raise ValueError
            code = body["error"]
            if not isinstance(code, str) or code not in SAFE_ERRORS | {
                "tool_execution_failed"
            }:
                raise ValueError
            raise BridgeError("tool_error:" + code)
        if set(body) != {"status", "fictional", "result"} or body["status"] != "ok":
            raise ValueError
        record = SalesReceipt.model_validate(body["result"])
        args = SalesQuery.model_validate(parameters)
        start, end = args.period()
        if (
            record.period.model_dump() != {"start": start, "end_exclusive": end}
            or record.customer_id != args.customer_id
        ):
            raise ValueError
        if (
            not record.read_only
            or record.total_yuan
            != f"{record.total_cents // 100}.{record.total_cents % 100:02d}"
        ):
            raise ValueError
        if record.rows_returned != len(record.orders) or len(record.orders) != min(
            record.order_count, args.limit
        ):
            raise ValueError
        if record.truncated != (record.order_count > len(record.orders)):
            raise ValueError
        if record.data_status != ("ok" if record.order_count else "no_data"):
            raise ValueError
        if not record.order_count and record.total_cents:
            raise ValueError
        if len({r.order_id for r in record.orders}) != len(record.orders):
            raise ValueError
        for row in record.orders:
            if row.status != "paid" or not start <= row.order_date < end:
                raise ValueError
            if args.customer_id is not None and row.customer_id != args.customer_id:
                raise ValueError
        subtotal = sum(row.amount_cents for row in record.orders)
        if subtotal > record.total_cents or (
            not record.truncated and subtotal != record.total_cents
        ):
            raise ValueError
        return record.model_dump()
    except BridgeError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError):
        raise BridgeError("invalid_mcp_receipt") from None


class McpSales:
    def __init__(self, client):
        self.client = client
        self.discovery = None
        self.calls = 0

    async def discover(self):
        try:
            with anyio.fail_after(5):
                listing = await self.client.list_tools()
            tools = listing.tools
            if len(tools) != 1 or listing.next_cursor is not None:
                raise ValueError
            tool = tools[0]
            if (
                tool.name != TOOL_NAME
                or tool.input_schema != SalesQuery.model_json_schema()
                or tool.output_schema != OUTPUT_SCHEMA
            ):
                raise ValueError
            if (
                self.client.protocol_version != "2026-07-28"
                or self.client.server_info.name != "day72-fictional-sales"
            ):
                raise ValueError
            if not tool.annotations or tool.annotations.read_only_hint is not True:
                raise ValueError
            self.discovery = {
                "server_name": self.client.server_info.name,
                "protocol_version": self.client.protocol_version,
                "tool_name": tool.name,
                "input_schema": copy.deepcopy(tool.input_schema),
            }
            # Descriptions and server instructions cannot change the host policy.
            return [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": "只读查询虚构销售数据；必须明确年份月份，不接受 SQL 或数据库路径。",
                        "parameters": copy.deepcopy(tool.input_schema),
                    },
                }
            ]
        except TimeoutError:
            raise BridgeError("mcp_discovery_timeout") from None
        except Exception:
            raise BridgeError("mcp_discovery_failed") from None

    async def query(self, arguments):
        if self.discovery is None:
            raise BridgeError("mcp_not_discovered")
        if self.calls:
            raise BridgeError("mcp_tool_budget_exhausted")
        self.calls += 1
        try:
            with anyio.fail_after(5):
                reply = await self.client.call_tool(TOOL_NAME, arguments)
        except TimeoutError:
            raise BridgeError("mcp_call_timeout") from None
        except MCPError:
            raise BridgeError("mcp_protocol_error") from None
        except Exception:
            raise BridgeError("mcp_transport_error") from None
        return validate_receipt(reply, arguments)
