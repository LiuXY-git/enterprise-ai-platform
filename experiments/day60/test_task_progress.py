"""Real SQLite checkpoint and separate-process recovery tests, fully offline."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("langgraph.checkpoint.sqlite", reason="Install Day 60 requirements")
pytest.importorskip("filelock", reason="Install Day 60 requirements")

from filelock import FileLock  # noqa: E402
from task_store import StoreError, TaskStore, normalize_plan, read_plan  # noqa: E402

HERE = Path(__file__).resolve().parent
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Day 60 must not access the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def cli(directory, *args, expected=0):
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(HERE / "task_progress.py"),
            "--store-dir",
            str(directory),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ENV,
        timeout=30,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return json.loads(result.stdout)


def count_checkpoints(store, task_id):
    with sqlite3.connect(store.database_path(task_id)) as conn:
        return conn.execute("SELECT count(*) FROM checkpoints").fetchone()[0]


def test_plan_progress_survives_separate_cli_processes(tmp_path):
    first = cli(tmp_path, "start")
    task_id = first["task_id"]
    assert first["thread_id"] == task_id
    assert first["phase"] == "paused" and first["progress"]["simulated"] == 0
    assert cli(tmp_path, "status", "--task-id", task_id) == first
    current = first
    for expected in range(1, 4):
        current = cli(
            tmp_path,
            "resume",
            "--task-id",
            task_id,
            "--checkpoint-id",
            current["checkpoint_id"],
        )
        assert current["task_id"] == task_id
        assert current["progress"]["simulated"] == expected
        assert cli(tmp_path, "status", "--task-id", task_id) == current
    assert current["status"] == "simulation_completed"
    assert current["phase"] == "finished"
    assert current["next_nodes"] == []
    assert current["trace"] == [
        "resume:S1",
        "simulate:S1",
        "resume:S2",
        "simulate:S2",
        "resume:S3",
        "simulate:S3",
        "finish",
    ]
    assert current["business_tools_executed"] is False


def test_stale_resume_never_advances_twice(tmp_path):
    store = TaskStore(tmp_path)
    initial = store.start(read_plan(None))
    once = store.resume(initial["task_id"], initial["checkpoint_id"])
    checkpoints = count_checkpoints(store, initial["task_id"])
    with pytest.raises(StoreError, match="stale_checkpoint"):
        store.resume(initial["task_id"], initial["checkpoint_id"])
    assert store.status(initial["task_id"]) == once
    assert count_checkpoints(store, initial["task_id"]) == checkpoints


def test_status_and_recover_do_not_advance_a_paused_task(tmp_path):
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    checkpoints = count_checkpoints(store, value["task_id"])
    assert store.status(value["task_id"]) == value
    assert store.recover(value["task_id"]) == value
    assert count_checkpoints(store, value["task_id"]) == checkpoints


def test_finished_task_is_not_replayed(tmp_path):
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    while value["phase"] == "paused":
        value = store.resume(value["task_id"], value["checkpoint_id"])
    count = count_checkpoints(store, value["task_id"])
    assert store.resume(value["task_id"], "old-checkpoint") == value
    assert store.recover(value["task_id"]) == value
    assert count_checkpoints(store, value["task_id"]) == count


def test_task_states_are_isolated(tmp_path):
    store = TaskStore(tmp_path)
    a, b = store.start(read_plan(None)), store.start(read_plan(None))
    assert a["task_id"] != b["task_id"]
    store.resume(a["task_id"], a["checkpoint_id"])
    assert store.status(b["task_id"]) == b


@pytest.mark.parametrize(
    "task_id", ["../enterprise_ai", "..\\other", "not-a-uuid", "", "1" * 32]
)
def test_invalid_task_id_is_rejected_without_creating_files(tmp_path, task_id):
    with pytest.raises(StoreError, match="invalid_task_id"):
        TaskStore(tmp_path).status(task_id)
    assert not list(tmp_path.iterdir())


def test_unknown_task_does_not_create_database(tmp_path):
    task_id = str(uuid4())
    with pytest.raises(StoreError, match="task_not_found"):
        TaskStore(tmp_path).status(task_id)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {
            "decision": "clarify",
            "summary": "Need input",
            "steps": [],
            "questions": ["What task?"],
        },
        {"artifact_type": "task_planning_result", "state": []},
    ],
)
def test_invalid_plan_never_creates_task(tmp_path, value):
    with pytest.raises(StoreError):
        TaskStore(tmp_path).start(value)
    assert not list(tmp_path.iterdir())


def test_accepts_valid_day59_result_and_rejects_failed_result():
    plan = read_plan(None)
    result = {
        "artifact_type": "task_planning_result",
        "state": {"status": "planned", "plan": plan},
    }
    assert normalize_plan(result) == plan
    result["state"]["status"] = "failed"
    with pytest.raises(StoreError, match="plan_not_ready"):
        normalize_plan(result)


def test_plan_file_missing_or_oversized(tmp_path):
    with pytest.raises(StoreError, match="invalid_plan_file"):
        read_plan(tmp_path / "missing.json")
    path = tmp_path / "oversized.json"
    path.write_text("x" * 65537, encoding="utf-8")
    with pytest.raises(StoreError, match="plan_file_too_large"):
        read_plan(path)


def test_checkpoint_and_plan_have_no_model_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "private-test-token")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    assert value["model_requests"] == 0
    assert "private-test-token" not in json.dumps(value)
    assert (
        b"private-test-token" not in store.database_path(value["task_id"]).read_bytes()
    )


def test_incompatible_graph_version_is_rejected(tmp_path):
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    with sqlite3.connect(store.database_path(value["task_id"])) as conn:
        conn.execute("UPDATE task_metadata SET graph_version = 999")
    with pytest.raises(StoreError, match="incompatible_task"):
        store.status(value["task_id"])


def test_task_lock_blocks_a_second_process(tmp_path):
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    with FileLock(str(store.database_path(value["task_id"])) + ".lock", timeout=0):
        result = cli(
            tmp_path,
            "resume",
            "--task-id",
            value["task_id"],
            "--checkpoint-id",
            value["checkpoint_id"],
            expected=1,
        )
    assert result["error"] == "task_busy"
    assert store.status(value["task_id"]) == value


def test_corrupt_metadata_returns_structured_cli_error(tmp_path):
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    with sqlite3.connect(store.database_path(value["task_id"])) as conn:
        conn.execute("UPDATE task_metadata SET plan_json = '{'")
    result = cli(tmp_path, "status", "--task-id", value["task_id"], expected=1)
    assert result == {"status": "error", "error": "invalid_task_database"}


def test_recover_after_forced_process_exit_preserves_committed_steps(tmp_path):
    # Commit S1 in one process; crash a different process during S2 before its update.
    value = cli(tmp_path, "start")
    value = cli(
        tmp_path,
        "resume",
        "--task-id",
        value["task_id"],
        "--checkpoint-id",
        value["checkpoint_id"],
    )
    script = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import progress_graph
from task_store import TaskStore
original = progress_graph.simulate_step
def crash(state):
    assert state['cursor'] == 1
    original(state)
    os._exit(77)
progress_graph.simulate_step = crash
TaskStore(Path(sys.argv[2])).resume(sys.argv[3], sys.argv[4])
"""
    crash = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            script,
            str(HERE),
            str(tmp_path),
            value["task_id"],
            value["checkpoint_id"],
        ],
        capture_output=True,
        env=ENV,
        timeout=30,
    )
    assert crash.returncode == 77, crash.stderr
    saved = cli(tmp_path, "status", "--task-id", value["task_id"])
    assert saved["phase"] == "recoverable"
    assert saved["progress"]["simulated"] == 1
    restored = cli(tmp_path, "recover", "--task-id", value["task_id"])
    assert restored["task_id"] == value["task_id"]
    assert restored["progress"]["simulated"] == 2
    assert restored["trace"].count("simulate:S1") == 1
    assert restored["trace"].count("simulate:S2") == 1
    assert restored["phase"] == "paused"
    final = cli(
        tmp_path,
        "resume",
        "--task-id",
        value["task_id"],
        "--checkpoint-id",
        restored["checkpoint_id"],
    )
    assert final["status"] == "simulation_completed"


def test_recover_initial_metadata_without_graph_checkpoint(tmp_path):
    store = TaskStore(tmp_path)
    value = store.start(read_plan(None))
    with sqlite3.connect(store.database_path(value["task_id"])) as conn:
        conn.execute("DELETE FROM writes")
        conn.execute("DELETE FROM checkpoints")
    assert store.status(value["task_id"])["phase"] == "initializing"
    recovered = store.recover(value["task_id"])
    assert recovered["phase"] == "paused" and recovered["progress"]["simulated"] == 0
