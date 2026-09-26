"""Bounded recovery for the fixed, read-only Day 73 MCP teaching workflow."""

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day78"))
import logged_agent as logged  # noqa: E402
from task_log import JournalError, TaskLog, read_log  # noqa: E402

agent = logged.agent
MAX_ATTEMPTS = 2
BACKOFF_SECONDS = 0.2
MODEL_TRANSIENT = frozenset(
    {
        "provider_timeout",
        "provider_network_error",
        "provider_http_502",
        "provider_http_503",
        "provider_http_504",
    }
)
TOOL_TRANSIENT = frozenset({"mcp_call_timeout", "mcp_transport_error"})
SCENARIOS = (
    "normal",
    "tool_timeout_once",
    "tool_timeout_always",
    "model_timeout_once",
    "report_timeout",
    "invalid_report",
    "invalid_arguments",
)


def safe_code(code):
    if code == "receipt_template_fallback":
        return code
    if code in MODEL_TRANSIENT or code in TOOL_TRANSIENT:
        return code
    return logged.safe_reason(code)


def retry_allowed(stage, code, attempt):
    allowed = (
        MODEL_TRANSIENT
        if stage == "model"
        else TOOL_TRANSIENT
        if stage == "tool"
        else ()
    )
    return type(attempt) is int and 1 <= attempt < MAX_ATTEMPTS and code in allowed


def recovery_decision(log, stage, code, attempt, *, retry):
    log.emit(
        "agent_decision",
        {
            "phase": "recovery",
            "stage": stage,
            "action": "retry" if retry else "stop",
            "attempt": attempt,
            "reason": safe_code(code),
            "next_attempt": attempt + 1 if retry else None,
            "backoff_ms": int(BACKOFF_SECONDS * 1000) if retry else 0,
            "policy": "fixed_readonly_snapshot"
            if stage == "tool"
            else "model_request_only",
        },
    )


class RecoveryChat:
    def __init__(self, chat, log, *, sleep=time.sleep):
        self.chat, self.log, self.sleep = chat, log, sleep
        self.attempts = 0
        self.retries = 0
        self.final_exhausted = False

    @property
    def requests(self):
        return getattr(self.chat, "requests", 0)

    @property
    def metadata(self):
        return {}

    def __call__(self, messages, tools, *, tool_choice="auto"):
        self.final_exhausted = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.log.emit(
                "model_started",
                {
                    "phase": "attempt",
                    "tool_choice": tool_choice,
                    "attempt": attempt,
                },
            )
            self.attempts += 1
            try:
                return self.chat(
                    copy.deepcopy(messages),
                    copy.deepcopy(tools),
                    tool_choice=tool_choice,
                )
            except agent.ToolChatError as exc:
                retry = retry_allowed("model", exc.code, attempt)
                self.log.emit(
                    "stage_error",
                    {
                        "stage": "model_attempt",
                        "attempt": attempt,
                        "reason": safe_code(exc.code),
                    },
                )
                recovery_decision(self.log, "model", exc.code, attempt, retry=retry)
                if not retry:
                    self.final_exhausted = (
                        tool_choice == "none"
                        and attempt == MAX_ATTEMPTS
                        and exc.code in MODEL_TRANSIENT
                    )
                    raise
                self.retries += 1
                self.sleep(BACKOFF_SECONDS)
        raise AssertionError("unreachable")


class McpTransport:
    """A fresh stdio connection and schema discovery for each attempt."""

    def __init__(self, database):
        self.database = database
        self.snapshot = hashlib.sha256(database.read_bytes()).hexdigest()
        self.dispatches = 0
        self.discovery = None

    def check_snapshot(self):
        if hashlib.sha256(self.database.read_bytes()).hexdigest() != self.snapshot:
            raise agent.BridgeError("database_changed")

    async def exchange(self, arguments=None):
        self.check_snapshot()
        stage = "connection"
        failure = None
        try:
            async with agent.Client(
                agent.server_parameters(self.database), read_timeout_seconds=5
            ) as client:
                bridge = agent.McpSales(client)
                try:
                    stage = "discovery"
                    definitions = await bridge.discover()
                    self.discovery = copy.deepcopy(bridge.discovery)
                    if arguments is None:
                        value = definitions
                    else:
                        stage = "query"
                        self.dispatches += 1
                        value = await bridge.query(copy.deepcopy(arguments))
                except agent.BridgeError as exc:
                    # Exit the stdio task group normally before propagating the
                    # classified error; otherwise a task group may wrap it.
                    failure = exc
                stage = "close"
            if failure is not None:
                raise failure
            return value
        except agent.BridgeError:
            raise
        except Exception:
            code = "mcp_close_failed" if stage == "close" else "mcp_connection_failed"
            raise agent.BridgeError(code) from None
        finally:
            self.check_snapshot()

    async def discover(self):
        return await self.exchange()

    async def query(self, arguments):
        return await self.exchange(arguments)


class RecoverySales:
    def __init__(self, transport, log, *, scenario="normal", sleep=agent.anyio.sleep):
        self.transport, self.log = transport, log
        self.scenario, self.sleep = scenario, sleep
        self.attempts = 0
        self.retries = 0
        self.used = False
        self.discovered = False

    @property
    def discovery(self):
        return self.transport.discovery

    async def discover(self):
        definitions = await self.transport.discover()
        self.discovered = True
        return definitions

    async def query(self, arguments):
        if self.used or not self.discovered:
            raise agent.BridgeError("mcp_tool_budget_exhausted")
        self.used = True
        original = copy.deepcopy(arguments)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self.log.emit(
                "tool_call",
                {
                    "phase": "attempt",
                    "call_ref": "T1",
                    "attempt": attempt,
                    "tool": agent.TOOL_NAME,
                    "arguments": original,
                    "snapshot_policy": "same_temporary_fictional_database",
                },
            )
            self.attempts += 1
            try:
                data = await self.transport.query(copy.deepcopy(original))
                # Teaching fault: a REAL read completed, but its reply is discarded.
                # Treat outcome as unknown to the agent; never imply non-execution.
                if self.scenario == "tool_timeout_always" or (
                    self.scenario == "tool_timeout_once" and attempt == 1
                ):
                    self.log.emit(
                        "stage_error",
                        {
                            "stage": "fault_injection",
                            "attempt": attempt,
                            "injection": "discard_validated_tool_reply_after_read",
                        },
                    )
                    raise agent.BridgeError("mcp_call_timeout")
                return data
            except agent.BridgeError as exc:
                retry = retry_allowed("tool", exc.code, attempt)
                self.log.emit(
                    "stage_error",
                    {
                        "stage": "tool_attempt",
                        "attempt": attempt,
                        "reason": safe_code(exc.code),
                        "outcome": "unknown_or_error",
                    },
                )
                recovery_decision(self.log, "tool", exc.code, attempt, retry=retry)
                if not retry:
                    raise
                self.retries += 1
                await self.sleep(BACKOFF_SECONDS)
        raise AssertionError("unreachable")


class ScenarioChat(agent.FixtureChat):
    def __init__(self, case, scenario):
        super().__init__(case)
        self.scenario = scenario
        self.calls = 0

    def __call__(self, messages, tools, *, tool_choice="auto"):
        self.calls += 1
        if (self.scenario == "model_timeout_once" and self.calls == 1) or (
            self.scenario == "report_timeout" and tool_choice == "none"
        ):
            raise agent.ToolChatError("provider_timeout")
        reply = super().__call__(messages, tools, tool_choice=tool_choice)
        if self.scenario == "invalid_report" and tool_choice == "none":
            report = json.loads(reply["message"]["content"])
            report["total_yuan"] = "9999.00"
            reply["message"]["content"] = json.dumps(report)
        if self.scenario == "invalid_arguments" and reply["message"].get("tool_calls"):
            arguments = {**agent.CASES[self.case]["scope"], "year": 2025}
            reply["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps(
                arguments
            )
        return reply


async def run_recovery(
    case,
    store,
    transport,
    chat,
    *,
    scenario="normal",
    live=False,
    model_sleep=time.sleep,
    tool_sleep=agent.anyio.sleep,
):
    if (
        case not in agent.CASES
        or scenario not in SCENARIOS
        or (live and scenario != "normal")
    ):
        raise ValueError("invalid_recovery_configuration")
    log = store.start(
        case,
        "live_model_real_mcp" if live else "fixture_model_real_mcp",
        agent.CASES[case]["goal"],
    )
    log.emit(
        "agent_decision",
        {
            "phase": "policy",
            "scenario": scenario,
            "fault_injection": scenario != "normal",
            "max_attempts_per_operation": MAX_ATTEMPTS,
            "fallback": "validated_receipt_template_after_final_model_transient_exhaustion",
        },
    )
    recovery_chat = RecoveryChat(chat, log, sleep=model_sleep)
    recovery_sales = RecoverySales(transport, log, scenario=scenario, sleep=tool_sleep)
    result = await agent.run_session(
        case,
        logged.LoggedChat(recovery_chat, log),
        logged.LoggedAdapter(recovery_sales, log),
        live=live,
    )
    if log.broken:
        raise JournalError("log_write_failed")
    unchanged = True
    try:
        transport.check_snapshot()
    except (OSError, agent.BridgeError):
        unchanged = False
        result.update(status="failed", stop_reason="database_changed", answer=None)
    fallback = (
        unchanged
        and recovery_chat.final_exhausted
        and result.get("receipt") is not None
        and result["stop_reason"] in MODEL_TRANSIENT
    )
    recovery_reason = safe_code(result["stop_reason"]) if fallback else None
    if fallback:
        # Only an already validated receipt from THIS task and scope is used.
        # No cached answer, host SQL bypass or rejected model text is accepted.
        report = agent.expected_report(result["receipt"], agent.CASES[case]["scope"])
        log.emit(
            "agent_decision",
            {
                "phase": "recovery",
                "action": "fallback",
                "source": "validated_receipt",
                "receipt_id": result["receipt"]["receipt_id"],
            },
        )
        result.update(
            status=report["status"],
            report=report,
            stop_reason="receipt_template_fallback",
            answer="模型回答服务暂不可用，以下为已校验回执的本地模板结果。\n"
            + agent.render(report),
        )
    elif result["stop_reason"] in MODEL_TRANSIENT:
        result.update(status="failed", answer=None)
    payload = {
        "status": result["status"],
        "stop_reason": safe_code(result["stop_reason"]),
        "answer": result["answer"],
        "agent_run_id": result["run_id"],
        "degraded": fallback,
        "recovery_reason": recovery_reason,
        "answer_source": "validated_receipt_fallback"
        if fallback
        else (
            "verified_report_template"
            if result.get("report") and result["answer"]
            else "clarification_template"
            if result["status"] == "needs_clarification"
            else "none"
        ),
        "logical_tool_calls": result["mcp_tool_attempts"],
        "tool_attempts": recovery_sales.attempts,
        "mcp_dispatches": transport.dispatches,
        "tool_retries": recovery_sales.retries,
        "model_attempts": recovery_chat.attempts,
        "model_retries": recovery_chat.retries,
        "model_requests": result["model_requests"],
        "tool_execution_outcome": result["tool_execution_outcome"],
        "database_unchanged": unchanged,
        "scenario": scenario,
        "next_action": "inspect_failure_before_new_task"
        if result["status"] in {"failed", "rejected"}
        else "none",
    }
    log.emit("final_answer", payload, status=payload["status"])
    return {"task_id": log.task_id, **payload}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-db", type=Path, default=ROOT / "data/day79/tasks.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--case", choices=agent.CASES, default="monthly")
    run.add_argument("--scenario", choices=SCENARIOS, default="normal")
    run.add_argument("--live", action="store_true")
    run.add_argument("--env-file", type=Path)
    commands.add_parser("list")
    show = commands.add_parser("show")
    show.add_argument("task_id")
    args = parser.parse_args()
    if args.command == "run":
        if args.live and args.scenario != "normal":
            parser.error("fault injection is fixture-only")
        if args.env_file and not args.live:
            parser.error("--env-file requires --live")
    try:
        if args.command != "run":
            result = read_log(args.log_db, getattr(args, "task_id", None))
        else:
            store = TaskLog(args.log_db)
            with tempfile.TemporaryDirectory(prefix="day79-fictional-") as directory:
                database = Path(directory) / "sales.sqlite"
                agent.create_demo(database)
                transport = McpTransport(database)
                chat = (
                    agent.ChatTools(args.env_file)
                    if args.live
                    else ScenarioChat(args.case, args.scenario)
                )

                async def selected():
                    return await run_recovery(
                        args.case,
                        store,
                        transport,
                        chat,
                        scenario=args.scenario,
                        live=args.live,
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
                    "notice": "Inspect persisted events; do not automatically restart.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
