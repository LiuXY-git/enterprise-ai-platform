"""Day 78: record the existing bounded MCP agent without changing frozen code."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from task_log import JournalError, TaskLog, read_log

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day73"))
import mcp_agent as agent  # noqa: E402

REASONS = {
    "report_verified",
    "missing_year_month",
    "tool_budget_exhausted",
    "multiple_tool_calls_rejected",
    "missing_scope",
    "tool_arguments_out_of_scope",
    "answer_without_tool_receipt",
    "invalid_clarification",
    "report_does_not_match_receipt",
    "invalid_model_report",
    "agent_execution_failed",
    "mcp_call_timeout",
    "mcp_transport_error",
    "mcp_protocol_error",
    "mcp_discovery_timeout",
    "mcp_discovery_failed",
    "invalid_mcp_receipt",
    "provider_timeout",
    "provider_network_error",
    "provider_invalid_response",
    "provider_incomplete_response",
    "configuration_invalid",
    "invalid_model_message",
    "response_too_large",
    "mcp_connection_failed",
    "mcp_close_failed",
    "database_changed",
}


def safe_reason(value):
    return (
        value if isinstance(value, str) and value in REASONS else "execution_rejected"
    )


class LoggedChat:
    def __init__(self, chat, log):
        self.chat, self.log = chat, log
        self.turn = 0

    @property
    def requests(self):
        return getattr(self.chat, "requests", 0)

    @property
    def metadata(self):
        # Credentials, provider responses and free-form metadata are not logged.
        return {}

    def __call__(self, messages, tools, *, tool_choice="auto"):
        self.turn += 1
        if tool_choice == "none" and messages[-1].get("role") == "tool":
            receipt = agent.parse_json(messages[-1]["content"])
            self.log.emit(
                "tool_feedback",
                {
                    "call_ref": "T1",
                    "receipt_id": receipt["receipt_id"],
                    "next_turn": self.turn,
                },
            )
        self.log.emit("model_started", {"turn": self.turn, "tool_choice": tool_choice})
        try:
            reply = self.chat(messages, tools, tool_choice=tool_choice)
            message, _ = agent.normalize_reply(reply)
        except Exception:
            self.log.emit("stage_error", {"stage": "model", "turn": self.turn})
            raise
        calls = message.get("tool_calls", [])
        # This is an observable proposal, not private reasoning or approval to run.
        self.log.emit(
            "agent_decision",
            {
                "turn": self.turn,
                "action": "request_tool" if calls else "propose_answer",
                "proposed_call_count": len(calls),
                "validation": "pending",
            },
        )
        return reply


class LoggedAdapter:
    def __init__(self, adapter, log):
        self.adapter, self.log = adapter, log

    @property
    def discovery(self):
        return self.adapter.discovery

    async def discover(self):
        self.log.emit("discovery_started", {"transport": "stdio"})
        try:
            definitions = await self.adapter.discover()
        except Exception:
            self.log.emit("stage_error", {"stage": "discovery"})
            raise
        self.log.emit("discovery_result", {"tool": agent.TOOL_NAME, "validated": True})
        return definitions

    async def query(self, arguments):
        # Day 73 has already checked the tool name, arguments and case scope.
        self.log.emit(
            "tool_call",
            {
                "call_ref": "T1",
                "tool": agent.TOOL_NAME,
                "arguments": arguments,
                "validation": "accepted",
            },
        )
        try:
            data = await self.adapter.query(arguments)
        except Exception:
            self.log.emit(
                "stage_error",
                {"stage": "tool", "call_ref": "T1", "outcome": "unknown_or_error"},
            )
            raise
        self.log.emit(
            "tool_result",
            {
                "call_ref": "T1",
                "validated": True,
                "fictional": True,
                "data_status": data["data_status"],
                "order_count": data["order_count"],
                "total_yuan": data["total_yuan"],
                "rows_returned": data["rows_returned"],
                "truncated": data["truncated"],
            },
        )
        return data


def finish(log, result, *, database_unchanged=None):
    if log.broken:
        raise JournalError("log_write_failed")
    status = result["status"]
    # Final answers come from the existing verified local template only.
    payload = {
        "status": status,
        "stop_reason": safe_reason(result["stop_reason"]),
        "answer": result.get("answer"),
        "agent_run_id": result.get("run_id"),
        "model_requests": result.get("model_requests", 0),
        "mcp_tool_attempts": result.get("mcp_tool_attempts", 0),
        "tool_execution_outcome": result.get("tool_execution_outcome", "not_attempted"),
        "database_unchanged": database_unchanged,
    }
    log.emit("final_answer", payload, status=status)
    return {"task_id": log.task_id, **payload}


async def execute(case, database, store, *, live=False, env_file=None):
    log = store.start(
        case,
        "live_model_real_mcp" if live else "fixture_model_real_mcp",
        agent.CASES[case]["goal"],
    )
    result = None
    chat = None
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    stage = "model_configuration"
    try:
        chat = agent.ChatTools(env_file) if live else agent.FixtureChat(case)
        stage = "connection"
        async with agent.Client(
            agent.server_parameters(database), read_timeout_seconds=5
        ) as client:
            stage = "session"
            result = await agent.run_session(
                case,
                LoggedChat(chat, log),
                LoggedAdapter(agent.McpSales(client), log),
                live=live,
            )
            stage = "close"
    except Exception:
        if log.broken:
            raise JournalError("log_write_failed") from None
        log.emit("stage_error", {"stage": stage})
        reason = {
            "close": "mcp_close_failed",
            "connection": "mcp_connection_failed",
            "model_configuration": "configuration_invalid",
        }.get(stage, "agent_execution_failed")
        result = {
            **(result or {}),
            "status": "failed",
            "stop_reason": reason,
            "answer": None,
            "model_requests": getattr(chat, "requests", 0),
        }
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    if before != after:
        result.update(status="failed", stop_reason="database_changed", answer=None)
    return finish(log, result, database_unchanged=before == after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-db", type=Path, default=ROOT / "data/day78/tasks.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--case", choices=agent.CASES, default="monthly")
    run.add_argument("--live", action="store_true")
    run.add_argument("--env-file", type=Path)
    commands.add_parser("list")
    show = commands.add_parser("show")
    show.add_argument("task_id")
    args = parser.parse_args()
    if args.command == "run" and args.env_file and not args.live:
        parser.error("--env-file requires --live")
    try:
        if args.command != "run":
            result = read_log(args.log_db, getattr(args, "task_id", None))
        else:
            store = TaskLog(args.log_db)
            with tempfile.TemporaryDirectory(prefix="day78-fictional-") as directory:
                database = Path(directory) / "sales.sqlite"
                agent.create_demo(database)

                async def selected():
                    return await execute(
                        args.case,
                        database,
                        store,
                        live=args.live,
                        env_file=args.env_file,
                    )

                result = agent.anyio.run(selected)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") in {"failed", "rejected"} else 0
    except (JournalError, OSError):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "task_log_or_file_unavailable",
                    "notice": "Inspect persisted events; do not assume completion.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
