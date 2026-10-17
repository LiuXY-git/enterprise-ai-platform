"""Exercise queue races, durable states, ownership and bounded subprocesses."""

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.console.config import ConsoleConfig
from backend.app.console.store import LeaseLost, QueueConflict, QueueFull, QueueStore
from backend.app.console.worker import Worker, child_environment


def request(message="中文 smoke"):
    return {"kind": "smoke", "mode": "fixture", "input": {"message": message}}


@pytest.fixture
def store(tmp_path):
    result = QueueStore(tmp_path / "jobs.sqlite")
    result.initialize()
    return result


def test_concurrent_idempotency_returns_one_durable_job(store):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.submit(request(), "same"), range(20)))
    assert len({job["job_id"] for job, _ in results}) == 1
    assert sum(not reused for _, reused in results) == 1
    again = QueueStore(store.path)
    assert again.list()["total"] == 1
    with pytest.raises(QueueConflict):
        again.submit(request("different"), "same")


def test_idempotency_precedes_queue_capacity_and_order_is_fifo(store):
    store.queue_limit = 2
    first, _ = store.submit(request("first"), "first")
    second, _ = store.submit(request("second"), "second")
    assert store.submit(request("first"), "first")[1]
    with pytest.raises(QueueFull):
        store.submit(request("third"), "third")
    assert store.acquire("worker", 15)
    assert store.claim("worker")["job_id"] == first["job_id"]
    assert store.claim("worker") is None
    store.finish(first["job_id"], "worker", result={"ok": True})
    assert store.claim("worker")["job_id"] == second["job_id"]
    assert store.list(status="succeeded")["total"] == 1
    assert len(store.list(limit=1, offset=1)["jobs"]) == 1


def test_single_active_worker_and_atomic_claim(store):
    job, _ = store.submit(request(), "claim")
    with ThreadPoolExecutor(max_workers=8) as pool:
        owners = list(pool.map(lambda n: (str(n), store.acquire(str(n), 15)), range(8)))
    winner = [owner for owner, acquired in owners if acquired]
    assert len(winner) == 1
    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(lambda _: store.claim(winner[0]), range(8)))
    assert [item["job_id"] for item in claimed if item] == [job["job_id"]]


def test_expired_lease_is_fenced_without_replaying_running_task(tmp_path):
    now = [100.0]
    store = QueueStore(tmp_path / "jobs.sqlite", clock=lambda: now[0])
    store.initialize()
    first, _ = store.submit(request(), "first")
    second, _ = store.submit(request("next"), "next")
    assert store.acquire("old", 15)
    store.claim("old")
    now[0] += 16
    assert store.worker_status()["status"] == "stale"
    # Reads do not mutate state or manufacture success.
    assert store.get(first["job_id"])["status"] == "running"
    with pytest.raises(LeaseLost):
        store.heartbeat("old", 15)
    assert store.acquire("new", 15)
    lost = store.get(first["job_id"])
    assert lost["status"] == "interrupted"
    assert lost["error"]["code"] == "worker_lease_expired"
    with pytest.raises(LeaseLost):
        store.finish(first["job_id"], "old", result={"late": True})
    store.release("old")
    assert store.worker_status()["status"] == "healthy"
    assert store.claim("new")["job_id"] == second["job_id"]


def test_heartbeat_extends_lease_and_release_marks_only_owned_job(tmp_path):
    now = [100.0]
    store = QueueStore(tmp_path / "jobs.sqlite", clock=lambda: now[0])
    store.initialize()
    assert store.worker_status()["status"] == "missing"
    job, _ = store.submit(request(), "first")
    store.acquire("worker", 15)
    store.claim("worker")
    now[0] += 10
    store.heartbeat("worker", 15)
    now[0] += 10
    assert not store.acquire("other", 15)
    store.release("worker")
    assert store.get(job["job_id"])["error"]["code"] == "worker_interrupted"
    assert store.worker_status()["status"] == "stopped"


def test_worker_executes_real_utf8_subprocess_and_persists_result(tmp_path):
    config = ConsoleConfig(tmp_path)
    store = QueueStore(config.database)
    store.initialize()
    message = "中文与引号 ' ; $(does-not-run)"
    job, _ = store.submit(request(message), "run")
    assert Worker(config).run(once=True) == 0
    result = QueueStore(config.database).get(job["job_id"])
    assert result["status"] == "succeeded"
    assert result["result"] == {"echo": message, "external_calls": 0}
    assert result["started_at"] and result["finished_at"]
    assert "owner" not in result and "request_key" not in result
    with pytest.raises(LeaseLost):
        store.finish(job["job_id"], "anyone", result={})


def test_second_worker_does_not_replace_first(store):
    config = ConsoleConfig(store.path.parent)
    assert store.acquire("existing", 15)
    assert Worker(config).run(once=True) == 2
    assert store.worker_status()["status"] == "healthy"


def test_child_environment_drops_secrets_and_python_injection(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "private")
    monkeypatch.setenv("PYTHONPATH", "injected")
    monkeypatch.setenv("PYTHONSTARTUP", "injected.py")
    assert (
        not {"DASHSCOPE_API_KEY", "PYTHONPATH", "PYTHONSTARTUP"}
        & child_environment().keys()
    )
    assert child_environment()["PYTHONUTF8"] == "1"


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("timeout", "task_timeout"),
        ("failure", "task_failed"),
        ("invalid", "invalid_task_result"),
        ("stop", "worker_interrupted"),
    ],
)
def test_failure_paths_kill_child_and_keep_safe_error(
    tmp_path, monkeypatch, mode, expected
):
    import backend.app.console.worker as module

    stop = threading.Event()
    config = ConsoleConfig(tmp_path)
    worker = Worker(config, stop=stop)
    worker.store.initialize()
    job, _ = worker.store.submit(request(), "failure")
    worker.store.acquire(worker.owner, config.lease_seconds)
    worker.store.claim(worker.owner)

    class Process:
        returncode = None
        killed = False

        def __init__(self, *args, **kwargs):
            if mode == "stop":
                stop.set()

        def communicate(self, **kwargs):
            if self.killed:
                return "", ""
            if mode == "timeout":
                raise subprocess.TimeoutExpired("fixed", 1)
            self.returncode = 1 if mode == "failure" else 0
            return "not json; private-secret", ""

        def poll(self):
            return self.returncode

        def kill(self):
            self.killed = True
            self.returncode = -9

    instance = Process()
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **kw: instance)
    ticks = iter([0, 0, 11]) if mode == "timeout" else iter([0, 0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    worker.execute(job)
    result = worker.store.get(job["job_id"])
    assert result["error"]["code"] == expected
    assert "private-secret" not in json.dumps(result)
    if mode in {"timeout", "stop"}:
        assert instance.killed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"queue_limit": 0},
        {"timeout_seconds": 0},
        {"lease_seconds": 1},
        {"poll_seconds": 2},
    ],
)
def test_invalid_server_configuration_rejected(tmp_path, kwargs):
    with pytest.raises(ValueError):
        ConsoleConfig(tmp_path, **kwargs)
