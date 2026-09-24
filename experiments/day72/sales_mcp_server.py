"""Expose the existing fictional read-only sales query over local MCP stdio."""

import argparse
import json
import logging
import sys
from pathlib import Path

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
    ToolAnnotations,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day65"))
from sales_sql import SalesError, SalesQuery, SalesTool  # noqa: E402

TOOL_NAME = "query_monthly_sales"
SAFE_ERRORS = {
    "invalid_query_parameters",
    "database_missing",
    "database_too_large",
    "database_schema_invalid",
    "database_query_failed",
    "database_unavailable",
    "query_budget_exceeded",
    "invalid_database_result",
}
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"const": "ok"},
        "fictional": {"const": True},
        "result": {"type": "object"},
    },
    "required": ["status", "fictional", "result"],
}


def result_message(payload: dict, *, error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, allow_nan=False),
            )
        ],
        structured_content=payload,
        is_error=error,
    )


def build_server(database: Path) -> Server:
    """The operator chooses the DB; MCP callers cannot supply SQL or file paths."""
    query_tool = SalesTool(database.resolve())
    query_slots = anyio.CapacityLimiter(1)

    async def list_tools(ctx, params):
        if params is not None and params.cursor is not None:
            raise MCPError(-32602, "invalid_cursor")
        return ListToolsResult(
            tools=[
                Tool(
                    name=TOOL_NAME,
                    description="只读查询教学虚构销售库的月度已支付订单。金额不代表真实企业销售额；不接受 SQL 或数据库路径。",
                    input_schema=SalesQuery.model_json_schema(),
                    output_schema=OUTPUT_SCHEMA,
                    annotations=ToolAnnotations(
                        read_only_hint=True, open_world_hint=False
                    ),
                )
            ]
        )

    async def call_tool(ctx, params):
        if params.name != TOOL_NAME:
            raise MCPError(-32602, "unknown_tool")
        try:
            # Low-level SDK advertises the schema but does not enforce it.
            # Use the original strict contract before any database access.
            args = SalesQuery.model_validate(params.arguments).model_dump()
        except (ValueError, TypeError, RecursionError):
            return result_message(
                {
                    "status": "error",
                    "fictional": True,
                    "error": "invalid_query_parameters",
                },
                error=True,
            )
        try:
            value = await anyio.to_thread.run_sync(
                query_tool.query, args, limiter=query_slots
            )
            return result_message({"status": "ok", "fictional": True, "result": value})
        except SalesError as exc:
            code = exc.code if exc.code in SAFE_ERRORS else "tool_execution_failed"
        except Exception:
            code = "tool_execution_failed"
        return result_message(
            {"status": "error", "fictional": True, "error": code}, error=True
        )

    return Server(
        "day72-fictional-sales",
        version="0.1.0",
        instructions="仅供教学；返回的是虚构销售数据。无订单不等于执行失败。",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve(database: Path) -> None:
    server = build_server(database)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="Operator-selected Day 65 fictional demo database",
    )
    args = parser.parse_args()
    # stdout belongs to the MCP protocol. Diagnostics go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    anyio.run(serve, args.db)


if __name__ == "__main__":
    main()
