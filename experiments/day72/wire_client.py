"""A standard-library JSON-RPC probe, independent of the MCP client SDK."""

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SERVER = Path(__file__).with_name("sales_mcp_server.py").resolve()
PROTOCOL = "2026-07-28"


def probe(database: Path) -> dict:
    database = database.resolve()
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "SYSTEMROOT",
            "WINDIR",
            "PATH",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "COMSPEC",
        }
    }
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    records = []
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errors:
        process = subprocess.Popen(
            [sys.executable, "-B", str(SERVER), "--db", str(database)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=SERVER.parent,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        lines = queue.Queue()

        def read_lines():
            while True:
                line = process.stdout.readline(65537)
                lines.put(line)
                if not line or len(line) > 65536:
                    break

        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()

        def request(method, params=None):
            request_id = len(records) + 1
            parameters = dict(params or {})
            parameters["_meta"] = {
                "io.modelcontextprotocol/protocolVersion": PROTOCOL,
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "day72-wire-probe",
                    "version": "0.1.0",
                },
            }
            message = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": parameters,
            }
            process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            process.stdin.flush()
            try:
                line = lines.get(timeout=5)
            except queue.Empty:
                raise TimeoutError("server_response_timeout") from None
            if not line or len(line) > 65536:
                raise ValueError("invalid_response_length")
            reply = json.loads(line)
            if reply.get("jsonrpc") != "2.0" or reply.get("id") != request_id:
                raise ValueError("unexpected_protocol_message")
            records.append({"request": message, "response": reply})
            return reply

        try:
            discovery = request("server/discover")["result"]
            if PROTOCOL not in discovery["supportedVersions"]:
                raise ValueError("unsupported_protocol")
            listing = request("tools/list")["result"]
            if [tool["name"] for tool in listing["tools"]] != ["query_monthly_sales"]:
                raise ValueError("unexpected_tools")
            result = request(
                "tools/call",
                {
                    "name": "query_monthly_sales",
                    "arguments": {"year": 2026, "month": 9, "limit": 2},
                },
            )["result"]
            if (
                result.get("isError", False)
                or result["structuredContent"]["result"]["total_yuan"] != "3000.00"
            ):
                raise ValueError("invalid_query_result")
            error = request(
                "tools/call",
                {
                    "name": "query_monthly_sales",
                    "arguments": {"year": 2026, "month": 13},
                },
            )["result"]
            if (
                not error["isError"]
                or error["structuredContent"]["error"] != "invalid_query_parameters"
            ):
                raise ValueError("invalid_argument_not_rejected")
            unknown = request(
                "tools/call", {"name": "delete_all_sales", "arguments": {}}
            )
            if unknown["error"]["code"] != -32602:
                raise ValueError("unknown_tool_not_rejected")
            empty = request(
                "tools/call",
                {
                    "name": "query_monthly_sales",
                    "arguments": {"year": 2026, "month": 7},
                },
            )["result"]
            if (
                empty.get("isError", False)
                or empty["structuredContent"]["result"]["data_status"] != "no_data"
            ):
                raise ValueError("connection_not_usable_after_errors")
            process.stdin.close()
            process.wait(timeout=5)
            if process.returncode != 0:
                raise ValueError("server_exit_failed")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            if not process.stdin.closed:
                process.stdin.close()
            reader.join(timeout=2)
            process.stdout.close()
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    if before != after:
        raise ValueError("database_changed")
    return {
        "status": "passed",
        "client": "stdlib_jsonrpc_without_mcp_client_sdk",
        "transport": "stdio",
        "protocol_version": PROTOCOL,
        "exchanges": records,
        "server_exit_code": process.returncode,
        "database_sha256_before": before,
        "database_sha256_after": after,
        "database_unchanged": True,
        "new_model_requests": 0,
        "external_service_requests": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, required=True, help="Existing unchanged Day 65 seed DB"
    )
    args = parser.parse_args()
    try:
        result = probe(args.db)
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
