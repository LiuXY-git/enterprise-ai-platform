"""Bounded retry policy, stop paths, validated fallback and real stdio checks."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recovery_agent as recovery  # noqa: E402

agent = recovery.agent


@pytest.fixture
def store(tmp_path):
    return recovery.TaskLog(tmp_path / "tasks.sqlite")


class Transport:
    discovery = {}

    def __init__(self, errors=(), *, changed=False, discovery_error=None):
        self.errors = list(errors)
        self.changed = changed
        self.discovery_error = discovery_error
        self.dispatches = 0
        self.arguments = []

    def check_snapshot(self):
        if self.changed:
            raise agent.BridgeError("database_changed")

    async def discover(self):
        if self.discovery_error:
            raise agent.BridgeError(self.discovery_error)
        return [{"type": "function", "function": {"name": agent.TOOL_NAME}}]

    async def query(self, arguments):
        self.dispatches += 1
        self.arguments.append(copy.deepcopy(arguments))
        if self.errors:
            code = self.errors.pop(0)
            if code:
                raise agent.BridgeError(code)
        return {
            "data_status": "ok",
            "order_count": 4,
            "total_yuan": "3000.00",
            "rows_returned": 2,
            "truncated": True,
        }


class Chat(agent.FixtureChat):
    def __init__(self, errors=(), case="monthly"):
        super().__init__(case)
        self.errors = list(errors)
        self.seen = []

    def __call__(self, messages, tools, *, tool_choice="auto"):
        self.seen.append(copy.deepcopy(messages))
        if self.errors:
            code = self.errors.pop(0)
            if code:
                raise agent.ToolChatError(code)
        return super().__call__(messages, tools, tool_choice=tool_choice)


def run(store, *, transport=None, chat=None, case="monthly", scenario="normal"):
    transport = transport or Transport()
    chat = chat or recovery.ScenarioChat(case, scenario)
    waits = []

    async def tool_sleep(delay):
        waits.append(("tool", delay))

    async def execute():
        return await recovery.run_recovery(
            case,
            store,
            transport,
            chat,
            scenario=scenario,
            model_sleep=lambda delay: waits.append(("model", delay)),
            tool_sleep=tool_sleep,
        )

    result = agent.anyio.run(execute)
    view = recovery.read_log(store.path, result["task_id"])
    return result, view, transport, chat, waits


@pytest.mark.parametrize(
    "stage,code,allowed",
    [
        ("tool", "mcp_call_timeout", True),
        ("tool", "mcp_transport_error", True),
        ("tool", "mcp_protocol_error", False),
        ("tool", "invalid_mcp_receipt", False),
        ("tool", "mcp_connection_failed", False),
        ("tool", "mcp_close_failed", False),
        ("tool", "tool_error:permission_denied", False),
        ("tool", "database_changed", False),
        ("tool", "mcp_discovery_failed", False),
        ("model", "provider_timeout", True),
        ("model", "provider_network_error", True),
        ("model", "provider_http_503", True),
        ("model", "provider_http_401", False),
        ("model", "provider_http_429", False),
        ("model", "configuration_invalid", False),
        ("model", "invalid_model_message", False),
        ("model", "provider_invalid_response", False),
        ("unknown", "provider_timeout", False),
    ],
)
def test_retry_allowlist(stage, code, allowed):
    assert recovery.retry_allowed(stage, code, 1) is allowed
    assert not recovery.retry_allowed(stage, code, 2)
    assert not recovery.retry_allowed(stage, code, 3)


@pytest.mark.parametrize("attempt", [0, -1, True, 1.0, "1"])
def test_invalid_attempt_budget(attempt):
    assert not recovery.retry_allowed("tool", "mcp_call_timeout", attempt)


@pytest.mark.parametrize("code", sorted(recovery.TOOL_TRANSIENT))
def test_tool_retry_same_arguments_without_replanning(store, code):
    result, view, transport, _, waits = run(store, transport=Transport([code]))
    assert result["status"] == "completed" and not result["degraded"]
    assert result["tool_attempts"] == 2 and result["logical_tool_calls"] == 1
    assert result["model_attempts"] == 2 and result["tool_retries"] == 1
    assert transport.arguments == [agent.CASES["monthly"]["scope"]] * 2
    assert waits == [("tool", 0.2)]
    assert any(e["payload"].get("action") == "retry" for e in view["events"])


def test_tool_exhaustion_never_fabricates_fallback(store):
    result, view, _, _, waits = run(
        store, transport=Transport(["mcp_call_timeout"] * 3)
    )
    assert result["status"] == "failed" and result["answer"] is None
    assert result["tool_attempts"] == 2 and result["model_attempts"] == 1
    assert result["tool_execution_outcome"] == "unknown"
    assert result["answer_source"] == "none" and not result["degraded"]
    assert len(waits) == 1 and view["terminal_recorded"]


@pytest.mark.parametrize(
    "code",
    [
        "mcp_protocol_error",
        "invalid_mcp_receipt",
        "mcp_close_failed",
        "tool_error:permission_denied",
        "mcp_connection_failed",
    ],
)
def test_tool_permanent_error_stops_once(store, code):
    result, _, _, _, waits = run(store, transport=Transport([code]))
    assert result["tool_attempts"] == 1 and result["tool_retries"] == 0
    assert result["answer"] is None and not result["degraded"]
    assert waits == []


@pytest.mark.parametrize("code", sorted(recovery.MODEL_TRANSIENT))
def test_model_retry_same_input(store, code):
    chat = Chat([code])
    result, _, _, chat, waits = run(store, chat=chat)
    assert result["status"] == "completed" and result["model_attempts"] == 3
    assert chat.seen[0] == chat.seen[1]
    assert result["tool_attempts"] == 1 and result["model_retries"] == 1
    assert waits == [("model", 0.2)]


def test_initial_model_exhaustion_has_no_receipt_fallback(store):
    result, _, transport, _, waits = run(store, chat=Chat(["provider_timeout"] * 3))
    assert result["status"] == "failed" and result["answer"] is None
    assert result["model_attempts"] == 2 and transport.dispatches == 0
    assert not result["degraded"] and len(waits) == 1


def test_final_timeout_uses_validated_receipt_without_requery(store):
    result, view, transport, _, _ = run(
        store, chat=Chat([None, "provider_timeout", "provider_timeout"])
    )
    assert result["status"] == "completed" and result["degraded"]
    assert "3000.00" in result["answer"] and "本地模板" in result["answer"]
    assert result["stop_reason"] == "receipt_template_fallback"
    assert result["recovery_reason"] == "provider_timeout"
    assert transport.dispatches == 1 and result["model_attempts"] == 3
    fallback = [e for e in view["events"] if e["payload"].get("action") == "fallback"]
    assert len(fallback) == 1
    assert fallback[0]["payload"]["receipt_id"] == result["agent_run_id"] + "/T1"


@pytest.mark.parametrize(
    "code",
    [
        "provider_http_401",
        "provider_http_429",
        "configuration_invalid",
        "provider_invalid_response",
        "invalid_model_message",
    ],
)
def test_final_permanent_model_error_cannot_fallback(store, code):
    result, _, transport, _, waits = run(store, chat=Chat([None, code]))
    assert result["status"] == "rejected" and result["answer"] is None
    assert result["model_attempts"] == 2 and transport.dispatches == 1
    assert result["model_retries"] == 0 and not result["degraded"] and waits == []


@pytest.mark.parametrize(
    "scenario,tool_calls", [("invalid_arguments", 0), ("invalid_report", 1)]
)
def test_invalid_contracts_cannot_be_retried_or_overridden(store, scenario, tool_calls):
    result, _, transport, _, waits = run(store, scenario=scenario)
    assert result["status"] == "rejected" and result["answer"] is None
    assert transport.dispatches == tool_calls and not result["degraded"]
    assert result["model_retries"] == result["tool_retries"] == 0 and waits == []


def test_database_change_blocks_fallback(store):
    result, _, _, _, _ = run(
        store,
        transport=Transport(changed=True),
        chat=Chat([None, "provider_timeout", "provider_timeout"]),
    )
    assert result["status"] == "failed" and not result["database_unchanged"]
    assert result["answer_source"] == "none" and result["answer"] is None
    assert not result["degraded"]


def test_discovery_failure_never_calls_model(store):
    result, _, _, _, waits = run(
        store, transport=Transport(discovery_error="mcp_discovery_failed")
    )
    assert result["model_attempts"] == result["tool_attempts"] == 0
    assert result["answer"] is None and waits == []


@pytest.mark.parametrize("action", ["retry", "fallback"])
def test_log_failure_prevents_recovery_action(store, monkeypatch, action):
    real_start = store.start
    ids = []

    def start(*args, **kwargs):
        log = real_start(*args, **kwargs)
        ids.append(log.task_id)
        emit = log.emit

        def guarded(kind, payload, **kw):
            if payload.get("action") == action:
                log.broken = True
                raise recovery.JournalError("disk_full")
            return emit(kind, payload, **kw)

        log.emit = guarded
        return log

    monkeypatch.setattr(store, "start", start)
    transport = Transport(["mcp_call_timeout"]) if action == "retry" else Transport()
    chat = (
        Chat()
        if action == "retry"
        else Chat([None, "provider_timeout", "provider_timeout"])
    )
    with pytest.raises(recovery.JournalError):
        run(store, transport=transport, chat=chat)
    assert transport.dispatches == 1
    assert not recovery.read_log(store.path, ids[0])["terminal_recorded"]


def test_unknown_error_text_not_persisted(store):
    result, view, _, _, _ = run(store, chat=Chat(["sk-private-credential"]))
    assert result["stop_reason"] == "execution_rejected"
    assert "sk-private-credential" not in json.dumps(view)
    assert b"sk-private-credential" not in store.path.read_bytes()


def test_recovery_adapter_cannot_start_second_logical_query(store):
    log = store.start("monthly", "fixture", "fixed goal")
    transport = Transport()
    adapter = recovery.RecoverySales(transport, log)

    async def execute():
        await adapter.discover()
        await adapter.query(agent.CASES["monthly"]["scope"])
        with pytest.raises(agent.BridgeError):
            await adapter.query(agent.CASES["monthly"]["scope"])

    agent.anyio.run(execute)
    assert transport.dispatches == 1


def test_actual_mcp_timeout_classification_survives_context_exit(
    store, tmp_path, monkeypatch
):
    database = tmp_path / "sales.sqlite"
    agent.create_demo(database)
    original = agent.McpSales.query
    calls = []

    async def lose_first_reply(self, arguments):
        data = await original(self, arguments)
        calls.append(copy.deepcopy(arguments))
        if len(calls) == 1:
            raise agent.BridgeError("mcp_call_timeout")
        return data

    monkeypatch.setattr(agent.McpSales, "query", lose_first_reply)
    result, _, transport, _, _ = run(store, transport=recovery.McpTransport(database))
    assert result["status"] == "completed" and result["tool_retries"] == 1
    assert transport.dispatches == 2 and len(calls) == 2
    assert result["database_unchanged"]


@pytest.mark.parametrize(
    "case,scenario,status,dispatches,degraded",
    [
        ("monthly", "normal", "completed", 1, False),
        ("monthly", "tool_timeout_once", "completed", 2, False),
        ("monthly", "tool_timeout_always", "failed", 2, False),
        ("monthly", "model_timeout_once", "completed", 1, False),
        ("monthly", "report_timeout", "completed", 1, True),
        ("monthly", "invalid_report", "rejected", 1, False),
        ("monthly", "invalid_arguments", "rejected", 0, False),
        ("empty", "report_timeout", "no_data", 1, True),
        ("clarification", "normal", "needs_clarification", 0, False),
    ],
)
def test_cli_recovery_and_readonly_replay(
    tmp_path, case, scenario, status, dispatches, degraded
):
    db = tmp_path / "task logs.sqlite"
    command = [sys.executable, "-B", str(Path(recovery.__file__)), "--log-db", str(db)]
    completed = subprocess.run(
        command + ["run", "--case", case, "--scenario", scenario],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == (1 if status in {"failed", "rejected"} else 0), (
        completed.stdout + completed.stderr
    )
    result = json.loads(completed.stdout)
    assert result["status"] == status and result["mcp_dispatches"] == dispatches
    assert result["degraded"] is degraded and result["model_requests"] == 0
    assert result["database_unchanged"]
    before = db.read_bytes()
    replay = subprocess.run(
        command + ["show", result["task_id"]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert replay.returncode == 0, replay.stderr
    view = json.loads(replay.stdout)
    assert view["terminal_recorded"] and view["task"]["status"] == status
    assert len(view["events"]) < 64 and db.read_bytes() == before


def test_live_fault_injection_rejected_before_database_creation(tmp_path):
    db = tmp_path / "never-created.sqlite"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(recovery.__file__)),
            "--log-db",
            str(db),
            "run",
            "--live",
            "--scenario",
            "report_timeout",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 2 and not db.exists()


def test_combined_maximum_budget_and_fallback(store):
    chat = Chat(["provider_timeout", None, "provider_timeout", "provider_timeout"])
    result, view, _, _, waits = run(
        store, chat=chat, transport=Transport(["mcp_call_timeout"])
    )
    assert result["status"] == "completed" and result["degraded"]
    assert result["model_attempts"] == 4 and result["tool_attempts"] == 2
    assert result["model_retries"] == 2 and result["tool_retries"] == 1
    assert len(waits) == 3 and len(view["events"]) < 64


def test_attempt_mutation_does_not_change_retried_parameters(store):
    class MutatingTransport(Transport):
        async def query(self, arguments):
            if not self.dispatches:
                self.dispatches += 1
                self.arguments.append(copy.deepcopy(arguments))
                arguments["year"] = 2025
                raise agent.BridgeError("mcp_transport_error")
            return await super().query(arguments)

    result, _, transport, _, _ = run(store, transport=MutatingTransport())
    assert result["status"] == "completed"
    assert transport.arguments == [agent.CASES["monthly"]["scope"]] * 2


def test_real_snapshot_change_prevents_dispatch(store, tmp_path):
    database = tmp_path / "sales.sqlite"
    agent.create_demo(database)
    transport = recovery.McpTransport(database)
    database.write_bytes(database.read_bytes() + b"changed")
    result, _, transport, _, _ = run(store, transport=transport)
    assert result["status"] == "failed" and result["stop_reason"] == "database_changed"
    assert transport.dispatches == 0 and result["model_attempts"] == 0


def test_close_failure_does_not_retry_or_accept_result(store, tmp_path, monkeypatch):
    database = tmp_path / "sales.sqlite"
    agent.create_demo(database)

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            raise RuntimeError("private transport details")

    monkeypatch.setattr(agent, "Client", Client)
    monkeypatch.setattr(agent, "McpSales", lambda client: Transport())
    result, view, transport, _, waits = run(
        store, transport=recovery.McpTransport(database)
    )
    assert result["answer"] is None and result["tool_retries"] == 0
    assert result["stop_reason"] == "mcp_close_failed"
    assert transport.dispatches == 0 and waits == []
    assert "private transport details" not in json.dumps(view)
