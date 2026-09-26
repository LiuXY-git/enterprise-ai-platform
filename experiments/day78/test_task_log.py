"""Durability, event ordering, rejection, failure and real subprocess replay."""

import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logged_agent as logged  # noqa: E402
from task_log import MAX_EVENTS, JournalError, TaskLog, read_log  # noqa: E402

agent = logged.agent


@pytest.fixture
def store(tmp_path):
    return TaskLog(tmp_path / "tasks.sqlite")


def start(store):
    return store.start("monthly", "fixture", agent.CASES["monthly"]["goal"])


def finish(log):
    log.emit("final_answer", {"answer": "done"}, status="completed")


class Adapter:
    """Unit-test only; integration tests below use a real MCP subprocess."""

    discovery = {}

    def __init__(self, error=None):
        self.error, self.calls = error, 0

    async def discover(self):
        if self.error == "discovery":
            raise agent.BridgeError("mcp_discovery_failed")
        return [{"type": "function", "function": {"name": agent.TOOL_NAME}}]

    async def query(self, arguments):
        self.calls += 1
        if self.error == "tool":
            raise agent.BridgeError("mcp_call_timeout")
        return {
            "data_status": "ok",
            "order_count": 4,
            "total_yuan": "3000.00",
            "rows_returned": 2,
            "truncated": True,
        }


class Chat(agent.FixtureChat):
    def __init__(self, fault=None):
        super().__init__("monthly")
        self.fault = fault
        self.calls = 0

    def __call__(self, messages, tools, *, tool_choice="auto"):
        self.calls += 1
        if self.fault == "exception":
            raise RuntimeError("sk-private-credential never log this")
        if self.fault == "malformed":
            return {"secret": "sk-private-credential"}
        reply = super().__call__(messages, tools, tool_choice=tool_choice)
        if self.fault == "scope" and tool_choice == "auto":
            reply["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps(
                {**agent.CASES["monthly"]["scope"], "year": 2025}
            )
        if self.fault == "secret" and tool_choice == "auto":
            reply["message"]["tool_calls"][0]["function"]["name"] = (
                "sk-private-credential"
            )
        if self.fault == "answer" and tool_choice == "none":
            data = json.loads(reply["message"]["content"])
            data["total_yuan"] = "9000.00"
            reply["message"]["content"] = json.dumps(data)
        return reply


def run_unit(store, *, chat=None, adapter=None, log=None):
    log = log or start(store)
    chat, adapter = chat or Chat(), adapter or Adapter()

    async def run():
        result = await agent.run_session(
            "monthly", logged.LoggedChat(chat, log), logged.LoggedAdapter(adapter, log)
        )
        return logged.finish(log, result)

    result = agent.anyio.run(run)
    return result, read_log(store.path, log.task_id), adapter, chat


def test_full_chain(store):
    result, view, adapter, chat = run_unit(store)
    assert result["status"] == "completed"
    assert adapter.calls == 1 and chat.calls == 2
    assert [e["kind"] for e in view["events"]] == [
        "user_request",
        "discovery_started",
        "discovery_result",
        "model_started",
        "agent_decision",
        "tool_call",
        "tool_result",
        "tool_feedback",
        "model_started",
        "agent_decision",
        "final_answer",
    ]
    assert "3000.00" in view["events"][-1]["payload"]["answer"]
    assert view["events"][4]["payload"]["validation"] == "pending"
    assert view["events"][5]["payload"]["validation"] == "accepted"
    assert [e["seq"] for e in view["events"]] == list(range(1, 12))
    assert view["events"][7]["payload"]["receipt_id"] == result["agent_run_id"] + "/T1"
    assert [e["elapsed_ms"] for e in view["events"]] == sorted(
        e["elapsed_ms"] for e in view["events"]
    )
    assert all(e["at"].endswith("+00:00") for e in view["events"])


@pytest.mark.parametrize(
    "fault", ["scope", "secret", "malformed", "exception", "answer"]
)
def test_rejection_and_secrets(store, fault):
    result, view, adapter, _ = run_unit(store, chat=Chat(fault))
    assert result["status"] == "rejected" and result["answer"] is None
    assert adapter.calls == (1 if fault == "answer" else 0)
    assert "sk-private-credential" not in json.dumps(view)
    assert b"sk-private-credential" not in store.path.read_bytes()
    assert view["terminal_recorded"]


@pytest.mark.parametrize("stage", ["discovery", "tool"])
def test_failure_is_replayable_without_retry(store, stage):
    result, view, adapter, _ = run_unit(store, adapter=Adapter(stage))
    assert result["answer"] is None
    errors = [e for e in view["events"] if e["kind"] == "stage_error"]
    assert errors[0]["payload"]["stage"] == stage
    assert adapter.calls == (1 if stage == "tool" else 0)
    if stage == "tool":
        assert result["status"] == "failed"
        assert result["tool_execution_outcome"] == "unknown"
        assert not any(e["kind"] == "tool_result" for e in view["events"])


def test_failure_before_tool_prevents_execution(store):
    log = start(store)
    original = log.emit

    def fail(kind, payload, **kwargs):
        if kind == "tool_call":
            log.broken = True
            raise JournalError("disk_full")
        return original(kind, payload, **kwargs)

    log.emit = fail
    adapter = Adapter()
    with pytest.raises(JournalError):
        run_unit(store, log=log, adapter=adapter)
    assert adapter.calls == 0
    assert read_log(store.path, log.task_id)["notice"] == "running_or_interrupted"


@pytest.mark.parametrize("boundary", ["tool_result", "final_answer"])
def test_write_failure_after_tool_never_reports_success(store, boundary):
    log = start(store)
    original = log.emit

    def fail(kind, payload, **kwargs):
        if kind == boundary:
            log.broken = True
            raise JournalError("disk_full")
        return original(kind, payload, **kwargs)

    log.emit = fail
    adapter = Adapter()
    with pytest.raises(JournalError):
        run_unit(store, log=log, adapter=adapter)
    assert adapter.calls == 1
    assert not read_log(store.path, log.task_id)["terminal_recorded"]


def test_sqlite_failure_marks_writer_broken(store):
    log = start(store)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TRIGGER no_events BEFORE INSERT ON events "
            "BEGIN SELECT RAISE(FAIL, 'full'); END"
        )
    with pytest.raises(JournalError):
        log.emit("model_started", {})
    assert log.broken
    assert len(read_log(store.path, log.task_id)["events"]) == 1


def test_terminal_event_and_status_are_atomic(store):
    log = start(store)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TRIGGER no_finish BEFORE UPDATE ON tasks "
            "BEGIN SELECT RAISE(FAIL, 'full'); END"
        )
    with pytest.raises(JournalError):
        finish(log)
    view = read_log(store.path, log.task_id)
    assert view["task"]["status"] == "running" and len(view["events"]) == 1


def test_terminal_cannot_be_appended(store):
    log = start(store)
    finish(log)
    with pytest.raises(JournalError):
        log.emit("model_started", {})
    assert len(read_log(store.path, log.task_id)["events"]) == 2


@pytest.mark.parametrize("payload", [[1], {"x": float("nan")}, {"x": "中" * 16384}])
def test_invalid_payload_not_written(store, payload):
    log = start(store)
    with pytest.raises(JournalError):
        log.emit("model_started", payload)
    assert len(read_log(store.path, log.task_id)["events"]) == 1


@pytest.mark.parametrize(
    "kind,status",
    [
        ("unrecognized", None),
        ("final_answer", None),
        ("model_started", "completed"),
        ("stage_error", "bad"),
    ],
)
def test_invalid_transition(store, kind, status):
    log = start(store)
    with pytest.raises(JournalError):
        log.emit(kind, {}, status=status)
    assert not read_log(store.path, log.task_id)["terminal_recorded"]


def test_event_limit(store):
    log = start(store)
    for _ in range(MAX_EVENTS - 1):
        log.emit("model_started", {})
    with pytest.raises(JournalError):
        log.emit("model_started", {})


def test_task_isolation_and_unique_concurrent_ids(store):
    def one(_):
        log = start(store)
        finish(log)
        return log.task_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(one, range(12)))
    assert len(set(ids)) == 12
    assert len(read_log(store.path)["tasks"]) == 12
    assert all(len(read_log(store.path, task_id)["events"]) == 2 for task_id in ids)


def test_read_does_not_create_or_mutate(tmp_path, store):
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(JournalError):
        read_log(missing)
    assert not missing.exists()
    log = start(store)
    before = store.path.read_bytes()
    with pytest.raises(JournalError):
        read_log(store.path, "' OR 1=1 --")
    assert read_log(store.path, log.task_id)["notice"] == "running_or_interrupted"
    assert store.path.read_bytes() == before


def test_unknown_database_is_not_adopted(tmp_path):
    path = tmp_path / "other.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE other(x)")
    before = path.read_bytes()
    with pytest.raises(JournalError):
        TaskLog(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("tamper", ["gap", "terminal", "json"])
def test_broken_log_detected(store, tamper):
    log = start(store)
    finish(log)
    with sqlite3.connect(store.path) as db:
        if tamper == "gap":
            db.execute("UPDATE events SET seq=8 WHERE seq=2")
        elif tamper == "terminal":
            db.execute("DELETE FROM events WHERE seq=2")
        else:
            db.execute("UPDATE events SET payload='not json'")
    with pytest.raises(JournalError):
        read_log(store.path, log.task_id)


@pytest.mark.parametrize(
    "case,status",
    [
        ("monthly", "completed"),
        ("customer", "completed"),
        ("empty", "no_data"),
        ("clarification", "needs_clarification"),
    ],
)
def test_cli_real_mcp_then_read_in_separate_process(tmp_path, case, status):
    path = tmp_path / "logs with spaces.sqlite"
    command = [sys.executable, "-B", str(Path(logged.__file__)), "--log-db", str(path)]
    run = subprocess.run(
        command + ["run", "--case", case],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["status"] == status and result["database_unchanged"]
    assert result["model_requests"] == 0
    before = path.read_bytes()
    replay = subprocess.run(
        command + ["show", result["task_id"]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert replay.returncode == 0, replay.stdout + replay.stderr
    view = json.loads(replay.stdout)
    assert view["terminal_recorded"] and view["task"]["status"] == status
    assert view["events"][-1]["payload"]["agent_run_id"] == result["agent_run_id"]
    assert path.read_bytes() == before
    if case == "clarification":
        assert not any(e["kind"] == "tool_call" for e in view["events"])


def test_interrupted_process_can_be_viewed(tmp_path):
    path = tmp_path / "interrupted.sqlite"
    code = (
        "from task_log import TaskLog; import sys; "
        "log=TaskLog(sys.argv[1]).start('monthly','fixture','fixed goal'); "
        "log.emit('tool_call', {'call_ref':'T1'}); print(log.task_id)"
    )
    run = subprocess.run(
        [sys.executable, "-B", "-c", code, str(path)],
        cwd=Path(logged.__file__).parent,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert run.returncode == 0, run.stderr
    view = read_log(path, run.stdout.strip())
    assert view["notice"] == "running_or_interrupted"
    assert view["events"][-1]["kind"] == "tool_call"
    assert not view["terminal_recorded"]


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("connection", "mcp_connection_failed"),
        ("close", "mcp_close_failed"),
        ("change", "database_changed"),
        ("configuration", "configuration_invalid"),
    ],
)
def test_outer_failure_prevents_success(store, tmp_path, monkeypatch, fault, reason):
    database = tmp_path / "fictional.sqlite"
    agent.create_demo(database)

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            if fault == "connection":
                raise RuntimeError("do not log provider details")
            return self

        async def __aexit__(self, *args):
            if fault == "close":
                raise RuntimeError("do not log close details")
            if fault == "change":
                database.write_bytes(database.read_bytes() + b"changed")

    monkeypatch.setattr(agent, "Client", Client)
    monkeypatch.setattr(agent, "McpSales", lambda client: Adapter())
    if fault == "configuration":

        def bad_config(case):
            raise RuntimeError("sk-private-credential")

        monkeypatch.setattr(agent, "FixtureChat", bad_config)

    async def run():
        return await logged.execute("monthly", database, store)

    result = agent.anyio.run(run)
    assert result["status"] == "failed" and result["answer"] is None
    assert result["stop_reason"] == reason
    view = read_log(store.path, result["task_id"])
    assert view["terminal_recorded"] and view["task"]["status"] == "failed"
    assert "sk-private-credential" not in json.dumps(view)


def test_show_never_opens_mcp_or_model(store, monkeypatch, capsys):
    log = start(store)
    finish(log)

    def forbidden(*args, **kwargs):
        pytest.fail("read-only replay must not start model or MCP")

    monkeypatch.setattr(agent, "Client", forbidden)
    monkeypatch.setattr(agent, "ChatTools", forbidden)
    monkeypatch.setattr(
        sys, "argv", ["logged_agent", "--log-db", str(store.path), "show", log.task_id]
    )
    assert logged.main() == 0
    assert json.loads(capsys.readouterr().out)["read_only"]


def test_live_counter_wrapper_without_network(store):
    class CountedChat(Chat):
        requests = 0

        def __call__(self, *args, **kwargs):
            self.requests += 1
            return super().__call__(*args, **kwargs)

    result, _, _, _ = run_unit(store, chat=CountedChat())
    assert result["model_requests"] == 2
