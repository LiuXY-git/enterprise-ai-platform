"""Launch a real stdio server and verify discovery, calls and error recovery."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import anyio
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.shared.exceptions import MCPError
from sales_mcp_server import TOOL_NAME, SalesQuery
from sales_sql import create_demo

SERVER = Path(__file__).with_name("sales_mcp_server.py").resolve()
CASES = (
    ("monthly", {"year": 2026, "month": 9, "limit": 2}, "3000.00", 4),
    ("customer", {"year": 2026, "month": 9, "customer_id": "C001"}, "1550.00", 2),
    ("no_sales", {"year": 2026, "month": 7}, "0.00", 0),
)
BAD_ARGS = (
    ("invalid_month", {"year": 2026, "month": 13}),
    ("string_year", {"year": "2026", "month": 9}),
    ("boolean_month", {"year": 2026, "month": True}),
    (
        "sql_injection_field",
        {"year": 2026, "month": 9, "sql": "DELETE FROM sales_orders"},
    ),
    ("database_path_field", {"year": 2026, "month": 9, "database": "secret.sqlite"}),
)


def server_parameters(database: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-B", str(SERVER), "--db", str(database.resolve())],
        env={"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        cwd=SERVER.parent,
    )


def binary_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def exercise(database: Path) -> dict:
    before = binary_sha(database)
    results = []
    with anyio.fail_after(30):
        async with Client(
            server_parameters(database), read_timeout_seconds=5
        ) as client:
            listing = await client.list_tools()
            if len(listing.tools) != 1 or listing.tools[0].name != TOOL_NAME:
                raise ValueError("unexpected_tool_inventory")
            tool = listing.tools[0]
            if tool.input_schema != SalesQuery.model_json_schema():
                raise ValueError("input_schema_changed")
            for case, args, total, count in CASES:
                reply = await client.call_tool(TOOL_NAME, args)
                body = reply.structured_content
                if reply.is_error or not body["fictional"]:
                    raise ValueError("unexpected_query_error")
                if (body["result"]["total_yuan"], body["result"]["order_count"]) != (
                    total,
                    count,
                ):
                    raise ValueError("unexpected_sales_result")
                if json.loads(reply.content[0].text) != body:
                    raise ValueError("text_and_structured_result_differ")
                results.append(
                    {"case": case, "is_error": reply.is_error, "payload": body}
                )
            for case, args in BAD_ARGS:
                reply = await client.call_tool(TOOL_NAME, args)
                if (
                    not reply.is_error
                    or reply.structured_content["error"] != "invalid_query_parameters"
                ):
                    raise ValueError("invalid_arguments_not_rejected")
                results.append(
                    {
                        "case": case,
                        "is_error": True,
                        "payload": reply.structured_content,
                    }
                )
            try:
                await client.call_tool("delete_all_sales", {})
            except MCPError as exc:
                if exc.code != -32602:
                    raise ValueError("unexpected_protocol_error") from None
                results.append({"case": "unknown_tool", "protocol_error": exc.code})
            else:
                raise ValueError("unknown_tool_not_rejected")
            recovered = await client.call_tool(TOOL_NAME, {"year": 2026, "month": 9})
            if (
                recovered.is_error
                or recovered.structured_content["result"]["total_yuan"] != "3000.00"
            ):
                raise ValueError("connection_failed_after_rejection")
            results.append({"case": "valid_after_errors", "is_error": False})
            protocol = client.protocol_version
            info = client.server_info.model_dump(mode="json", by_alias=True)
    after = binary_sha(database)
    if before != after:
        raise ValueError("database_changed")
    return {
        "status": "passed",
        "transport": "stdio",
        "server_process": "real_child_process",
        "protocol_version": protocol,
        "server_info": info,
        "tool": tool.model_dump(mode="json", by_alias=True, exclude_none=True),
        "cases": results,
        "database_sha256_before": before,
        "database_sha256_after": after,
        "database_unchanged": True,
        "fictional_data": True,
        "new_model_requests": 0,
        "external_service_requests": 0,
        "agent_model_integration": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        help="Existing, unmodified Day 65 seed DB; otherwise create a temporary demo",
    )
    args = parser.parse_args()
    try:
        if args.db:
            result = anyio.run(exercise, args.db)
        else:
            with tempfile.TemporaryDirectory(prefix="day72-mcp-") as directory:
                database = Path(directory) / "fictional.sqlite"
                create_demo(database)
                result = anyio.run(exercise, database)
    except Exception as exc:
        print(
            json.dumps({"status": "failed", "error": type(exc).__name__}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
