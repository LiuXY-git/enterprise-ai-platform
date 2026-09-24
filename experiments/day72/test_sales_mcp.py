"""Exercise MCP contracts and real stdio, not just the SQL function."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from jsonschema import validate as validate_json
from mcp import Client
from mcp.shared.exceptions import MCPError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sales_mcp_server import (  # noqa: E402
    OUTPUT_SCHEMA,
    TOOL_NAME,
    SalesError,
    SalesQuery,
    SalesTool,
    build_server,
)
from sales_sql import create_demo  # noqa: E402
from smoke_client import binary_sha, exercise, server_parameters  # noqa: E402
from wire_client import probe  # noqa: E402


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "fictional.sqlite"
    create_demo(path)
    return path


def call(database, arguments, name=TOOL_NAME):
    async def run():
        async with Client(build_server(database)) as client:
            return await client.call_tool(name, arguments)

    return anyio.run(run)


def test_discovery_contract(database):
    async def run():
        async with Client(build_server(database)) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 1
            tool = tools[0]
            assert tool.name == TOOL_NAME
            assert tool.input_schema == SalesQuery.model_json_schema()
            assert tool.input_schema["additionalProperties"] is False
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.open_world_hint is False
            assert tool.output_schema == OUTPUT_SCHEMA
            assert client.protocol_version == "2026-07-28"
            assert client.server_info.name == "day72-fictional-sales"

    anyio.run(run)


@pytest.mark.parametrize(
    "args,total,count",
    [
        ({"year": 2026, "month": 9, "limit": 2}, "3000.00", 4),
        ({"year": 2026, "month": 9, "customer_id": "C001"}, "1550.00", 2),
        ({"year": 2026, "month": 7}, "0.00", 0),
        ({"year": 2026, "month": 9, "customer_id": "C999"}, "0.00", 0),
    ],
)
def test_query_result_over_protocol(database, args, total, count):
    before = binary_sha(database)
    reply = call(database, args)
    assert not reply.is_error
    payload = reply.structured_content
    validate_json(payload, OUTPUT_SCHEMA)
    assert payload["fictional"]
    assert payload["result"]["total_yuan"] == total
    assert payload["result"]["order_count"] == count
    assert payload["result"]["data_status"] == ("ok" if count else "no_data")
    assert payload["result"]["read_only"]
    assert json.loads(reply.content[0].text) == payload
    assert before == binary_sha(database)


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"year": 2026},
        {"year": "2026", "month": 9},
        {"year": True, "month": 9},
        {"year": 2026, "month": True},
        {"year": 2026, "month": 9.0},
        {"year": 2026, "month": 0},
        {"year": 2026, "month": 13},
        {"year": 2019, "month": 9},
        {"year": 2101, "month": 9},
        {"year": 2026, "month": 9, "limit": 0},
        {"year": 2026, "month": 9, "limit": 21},
        {"year": 2026, "month": 9, "customer_id": "C001' OR 1=1--"},
        {"year": 2026, "month": 9, "sql": "DELETE FROM sales_orders"},
        {"year": 2026, "month": 9, "database": "secret.sqlite"},
    ],
)
def test_invalid_parameters_rejected_before_database(database, monkeypatch, args):
    touched = []
    monkeypatch.setattr(SalesTool, "query", lambda *a: touched.append(True))
    reply = call(database, args)
    assert reply.is_error
    assert reply.structured_content["error"] == "invalid_query_parameters"
    assert not touched
    assert "DELETE" not in reply.content[0].text
    assert "secret.sqlite" not in reply.content[0].text


def test_unknown_tool_rejected_before_database(database, monkeypatch):
    touched = []
    monkeypatch.setattr(SalesTool, "query", lambda *a: touched.append(True))

    async def run():
        async with Client(build_server(database)) as client:
            with pytest.raises(MCPError) as error:
                await client.call_tool("delete_all_sales", {})
            assert error.value.code == -32602

    anyio.run(run)
    assert not touched


@pytest.mark.parametrize("kind", ["missing", "wrong_schema", "corrupt"])
def test_database_fault_is_error_not_zero_sales(tmp_path, kind):
    path = tmp_path / "private-file.sqlite"
    if kind == "wrong_schema":
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE secrets(value TEXT)")
    elif kind == "corrupt":
        path.write_text("not a database", encoding="utf-8")
    before = binary_sha(path) if path.exists() else None
    reply = call(path, {"year": 2026, "month": 9})
    assert reply.is_error
    assert "result" not in reply.structured_content
    assert "private-file" not in reply.content[0].text
    assert "secrets" not in reply.content[0].text
    assert (binary_sha(path) if path.exists() else None) == before


@pytest.mark.parametrize(
    "error,expected",
    [
        (SalesError("query_budget_exceeded"), "query_budget_exceeded"),
        (SalesError("secret-password"), "tool_execution_failed"),
        (RuntimeError("private/path/password"), "tool_execution_failed"),
    ],
)
def test_execution_errors_are_bounded_and_sanitized(
    database, monkeypatch, error, expected
):
    def fail(*args):
        raise error

    monkeypatch.setattr(SalesTool, "query", fail)
    reply = call(database, {"year": 2026, "month": 9})
    assert reply.is_error
    assert reply.structured_content["error"] == expected
    assert "password" not in reply.content[0].text


def test_real_sdk_stdio_client(database):
    result = anyio.run(exercise, database)
    assert result["status"] == "passed"
    assert len(result["cases"]) == 10
    assert result["database_unchanged"]
    assert not result["agent_model_integration"]


def test_independent_raw_wire_client_and_eof_shutdown(database):
    result = probe(database)
    assert result["status"] == "passed"
    assert len(result["exchanges"]) == 6
    assert result["server_exit_code"] == 0
    assert result["database_unchanged"]


def test_missing_database_error_crosses_real_stdio(tmp_path):
    path = tmp_path / "absent.sqlite"

    async def run():
        with anyio.fail_after(15):
            async with Client(
                server_parameters(path), read_timeout_seconds=5
            ) as client:
                reply = await client.call_tool(TOOL_NAME, {"year": 2026, "month": 9})
                assert reply.is_error
                assert reply.structured_content["error"] == "database_missing"

    anyio.run(run)
    assert not path.exists()


def test_cli_from_another_working_directory(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).with_name("smoke_client.py"))],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        timeout=40,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "passed"


def test_new_database_setup_refuses_overwrite(database):
    before = binary_sha(database)
    with pytest.raises(SalesError, match="database_already_exists"):
        create_demo(database)
    assert binary_sha(database) == before
