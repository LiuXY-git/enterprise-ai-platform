"""Execution isolation, interrupted evidence and separation from business judgement."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.day86 import dataset_tool as datasets  # noqa: E402
from experiments.day87 import runner, worker  # noqa: E402
from experiments.day87.execution_contracts import (  # noqa: E402
    ExecutionRow,
    Observations,
    WorkerResult,
)


def observed(status="completed"):
    return Observations(
        business_status=status,
        task_id="a" * 32,
        agent_run_id="b" * 32,
        stop_reason="test_observation",
        answer="fixture",
        answer_source="fixture",
        tool_attempts=1,
        mcp_dispatches=1,
        tool_retries=0,
        model_attempts=2,
        model_retries=0,
        model_requests=0,
        degraded=False,
        database_unchanged=True,
        approval_status=None,
        simulated_effects=0,
        external_send=False,
        event_count=1,
    )


@pytest.fixture
def isolated(monkeypatch):
    dataset = datasets.load_dataset()
    agent = datasets.AgentSpec.model_validate(datasets.read_json(datasets.AGENT))

    def preparation(_dataset, _agent, suite):
        return (
            datasets.make_plan(dataset, agent, suite),
            {"status": "passed", "test_double": True},
            {},
        )

    monkeypatch.setattr(runner, "prepare", preparation)


def fake_worker(command, directory, timeout, *, status="completed"):
    cid = command[command.index("--case-id") + 1]
    key = command[command.index("--case") + 1]
    scenario = command[command.index("--scenario") + 1]
    result = WorkerResult(
        protocol="day87-worker-v1",
        case_id=cid,
        case=key,
        scenario=scenario,
        observations=observed(status),
    )
    datasets.save(directory / "worker-result.json", result.model_dump())
    (directory / "artifacts").mkdir()
    for filename in [
        "generation.json",
        "events.json",
        "fictional.sqlite",
        "tasks.sqlite",
    ]:
        (directory / "artifacts" / filename).write_text("fixture", encoding="utf-8")
    assert "--live" not in command and "--expected" not in command
    assert "--dataset" not in command
    return dict(code=0, error=None, cleanup=None)


def test_business_rejection_is_completed_execution_not_score(
    tmp_path, monkeypatch, isolated
):
    monkeypatch.setattr(
        runner, "run_process", lambda *a: fake_worker(*a, status="rejected")
    )
    report = runner.run(tmp_path / "run", suite="smoke")
    assert report["run_status"] == "completed"
    assert report["summary"]["completed"] == 4
    assert report["summary"]["business_status_counts"] == {"rejected": 4}
    assert report["summary"]["success_rate"] is None
    assert all(
        row["judgement"] == "not_evaluated" and row["metrics"]["cost"] is None
        for row in report["rows"]
    )
    assert runner.inspect(tmp_path / "run")["status"] == "evidence_consistent"


@pytest.mark.parametrize(
    "failure",
    ["crash", "timeout", "malformed", "missing", "wrong_identity", "start_failed"],
)
def test_one_case_failure_does_not_block_others(
    tmp_path, monkeypatch, isolated, failure
):
    calls = []

    def execute(command, directory, timeout):
        calls.append(directory.name)
        if len(calls) != 1:
            return fake_worker(command, directory, timeout)
        if failure == "crash":
            return dict(code=3, error=None, cleanup=None)
        if failure == "timeout":
            return dict(code=-1, error="case_timeout", cleanup=True)
        if failure == "start_failed":
            return dict(code=None, error="worker_start_failed", cleanup=None)
        result = fake_worker(command, directory, timeout)
        if failure == "malformed":
            (directory / "worker-result.json").write_text("invalid", encoding="utf-8")
        elif failure == "missing":
            (directory / "artifacts/events.json").unlink()
        else:
            data = datasets.read_json(directory / "worker-result.json")
            data["case_id"] = "another_case"
            datasets.save(directory / "worker-result.json", data)
        return result

    monkeypatch.setattr(runner, "run_process", execute)
    report = runner.run(tmp_path / "run", suite="smoke")
    assert len(calls) == 4 and len(set(calls)) == 4
    assert report["run_status"] == "completed_with_errors"
    assert report["summary"]["completed"] == 3
    assert report["summary"]["errors"] + report["summary"]["timeouts"] == 1
    assert report["rows"][0]["observed"] is None
    assert runner.inspect(tmp_path / "run")["status"] == "evidence_consistent"


@pytest.mark.parametrize(
    "error,cleanup", [("user_interrupted", True), ("cleanup_failed", False)]
)
def test_interrupt_or_uncertain_cleanup_stops_batch(
    tmp_path, monkeypatch, isolated, error, cleanup
):
    calls = []

    def execute(*args):
        calls.append(1)
        return dict(code=-1, error=error, cleanup=cleanup)

    monkeypatch.setattr(runner, "run_process", execute)
    report = runner.run(tmp_path / "run", suite="smoke")
    assert len(calls) == 1
    assert report["run_status"] == "interrupted"
    assert report["summary"]["not_run"] == 3
    assert report["rows"][0]["cleanup_verified"] is cleanup
    assert runner.inspect(tmp_path / "run")["run_status"] == "interrupted"


def test_no_overwrite_or_resume(tmp_path, monkeypatch):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "report.json").write_text("old evidence", encoding="utf-8")

    def forbidden(*args):
        raise AssertionError("preflight should not start")

    monkeypatch.setattr(runner, "prepare", forbidden)
    with pytest.raises(FileExistsError):
        runner.run(output)
    assert (output / "report.json").read_text() == "old evidence"


@pytest.mark.parametrize("timeout", [0, 4, 121, True, 10.0])
def test_timeout_bounds_checked_before_creation(tmp_path, timeout):
    with pytest.raises(ValueError):
        runner.run(tmp_path / "run", timeout=timeout)
    assert not (tmp_path / "run").exists()


def test_invalid_dataset_never_starts_worker(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    datasets.save(bad, {"secret": "never-echo"})

    def forbidden(*args, **kwargs):
        raise AssertionError("worker should not start")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(ValueError):
        runner.run(tmp_path / "run", dataset=bad)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "artifact",
        "extra_artifact",
        "result",
        "summary",
        "plan_hash",
        "score",
        "metrics",
        "coverage",
        "terminal",
    ],
)
def test_audit_rejects_modified_or_false_evidence(
    tmp_path, monkeypatch, isolated, mutation
):
    monkeypatch.setattr(runner, "run_process", fake_worker)
    out = tmp_path / "run"
    report = runner.run(out, suite="smoke")
    case = out / "cases/monthly_normal"
    if mutation == "artifact":
        (case / "artifacts/events.json").write_text("changed", encoding="utf-8")
    elif mutation == "extra_artifact":
        (case / "unexpected.txt").write_text("extra", encoding="utf-8")
    elif mutation == "result":
        datasets.save(case / "result.json", {})
    else:
        if mutation == "summary":
            report["summary"]["completed"] = 5
        elif mutation == "plan_hash":
            report["plan_sha256"] = "0" * 64
        elif mutation == "score":
            report["summary"]["success_rate"] = 1.0
        elif mutation == "metrics":
            report["rows"][0]["metrics"]["input_tokens"] = 0
        elif mutation == "coverage":
            report["rows"].pop()
        else:
            report["rows"][0]["observed"] = None
        datasets.save(out / "report.json", report)
    with pytest.raises(ValueError):
        runner.inspect(out)


def test_inspect_does_not_execute_or_reimport_runtime(tmp_path, monkeypatch, isolated):
    monkeypatch.setattr(runner, "run_process", fake_worker)
    out = tmp_path / "run"
    runner.run(out, suite="smoke")

    def forbidden(*args, **kwargs):
        raise AssertionError("inspection must not execute")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert runner.inspect(out)["agent_executed"] is False


@pytest.mark.parametrize(
    "relative", ["../outside.json", "/outside.json", "nested/../../outside.json"]
)
def test_artifact_path_containment(tmp_path, relative):
    with pytest.raises(ValueError):
        runner.contained(tmp_path, relative)


def test_worker_rejects_arbitrary_pair_before_import(tmp_path):
    with pytest.raises(ValueError):
        worker.execute("bad", "clarification", "report_timeout", tmp_path)


def test_worker_observations_come_from_trace_not_golden(tmp_path):
    o = observed("rejected")
    generation = o.model_dump()
    generation["status"] = generation.pop("business_status")
    trace = dict(generation=generation, approval=None, external_send=False)
    journal = dict(
        terminal_recorded=True,
        task={"task_id": o.task_id},
        events=[{"kind": "final_answer", "payload": {"status": "rejected"}}],
    )
    result = worker.collect(trace, journal, tmp_path)
    assert result.business_status == "rejected" and result.answer == "fixture"
    journal["task"]["task_id"] = "c" * 32
    with pytest.raises(ValueError):
        worker.collect(trace, journal, tmp_path)


def test_real_child_timeout_cleanup(tmp_path):
    # The parent creates a grandchild; /T must clear both, not just the waiter.
    child_pid = tmp_path / "grandchild.pid"
    program = (
        "import subprocess,sys,time; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"Path({str(child_pid)!r}).write_text(str(p.pid)); time.sleep(30)"
    )
    result = runner.run_process([sys.executable, "-c", program], tmp_path, 1)
    assert result["error"] == "case_timeout"
    assert result["cleanup"] is True
    assert result["code"] is not None
    assert child_pid.exists()
    pid = int(child_pid.read_text())
    if sys.platform == "win32":
        import ctypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            code = ctypes.c_ulong()
            try:
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                assert code.value != 259  # STILL_ACTIVE
            finally:
                kernel.CloseHandle(handle)


def test_cleanup_denial_stops_direct_child_without_false_tree_claim(monkeypatch):
    from types import SimpleNamespace

    class Process:
        pid = 1234
        returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -1

        def wait(self, timeout):
            return self.returncode

    process = Process()
    monkeypatch.setattr(runner.os, "name", "nt")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1)
    )
    assert runner.stop_tree(process) is False
    assert process.returncode == -1


def test_real_start_error_captured(tmp_path):
    result = runner.run_process([str(tmp_path / "nonexistent-executable")], tmp_path, 1)
    assert result == dict(code=None, error="worker_start_failed", cleanup=None)


def test_row_contract_rejects_false_success():
    with pytest.raises(ValueError):
        ExecutionRow(case_id="test", execution_status="completed")
    with pytest.raises(ValueError):
        ExecutionRow(case_id="test", execution_status="error")
