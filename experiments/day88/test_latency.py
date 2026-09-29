"""Known clocks, separated censored samples, schema integrity and regression boundaries."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.day87 import runner as base  # noqa: E402
from experiments.day87 import test_runner as fixtures  # noqa: E402
from experiments.day88 import runner  # noqa: E402
from experiments.day88.latency import (
    LatencyMetrics,
    TimedReport,
    TimedRow,
    aggregate,
    describe,
)  # noqa: E402


def row(status, ns=None, business="completed"):
    data = dict(case_id="sample", execution_status=status)
    if status == "completed":
        data.update(observed=fixtures.observed(business), worker_exit_code=0)
    elif status not in {"not_run", "running"}:
        data["error"] = (
            "case_timeout"
            if status == "timeout"
            else "user_interrupted"
            if status == "interrupted"
            else "worker_exit_nonzero"
        )
    if ns is not None:
        data["metrics"] = dict(
            elapsed_ns=ns,
            latency_ms=round(ns / 1e6, 3),
            measurement="complete_case" if status == "completed" else "partial_case",
        )
    return TimedRow.model_validate(data)


def test_known_percentiles_and_zero_samples():
    assert describe([]) == dict(
        samples=0, min_ms=None, mean_ms=None, p50_ms=None, p95_ms=None, max_ms=None
    )
    stats = describe([n * 1_000_000 for n in range(1, 21)])
    assert stats == dict(
        samples=20, min_ms=1.0, mean_ms=10.5, p50_ms=10.0, p95_ms=19.0, max_ms=20.0
    )
    assert describe([1234567])["p95_ms"] == 1.235


def test_failure_and_timeout_not_mixed_with_completed_latency():
    summary = aggregate(
        [
            row("completed", 10_000_000),
            row("completed", 30_000_000, "rejected"),
            row("timeout", 100_000_000),
            row("error", 1_000_000),
            row("not_run"),
            row("interrupted"),
        ]
    )
    assert summary["measured_cases"] == 4 and summary["unmeasured_cases"] == 2
    assert summary["sum_case_elapsed_ms"] == 141.0
    assert summary["by_execution_status"]["completed"]["mean_ms"] == 20.0
    assert summary["by_execution_status"]["timeout"]["mean_ms"] == 100.0
    assert summary["by_business_status"]["rejected"]["samples"] == 1
    assert summary["by_business_status"]["failed"]["mean_ms"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "negative",
        "bool",
        "nan",
        "infinity",
        "wrong_conversion",
        "fake_missing",
        "wrong_kind",
        "tokens",
    ],
)
def test_metric_contract_rejects_false_values(mutation):
    data = dict(elapsed_ns=1_000_000, latency_ms=1.0, measurement="complete_case")
    if mutation == "negative":
        data["elapsed_ns"] = -1
    elif mutation == "bool":
        data["elapsed_ns"] = True
    elif mutation == "nan":
        data["latency_ms"] = float("nan")
    elif mutation == "infinity":
        data["latency_ms"] = float("inf")
    elif mutation == "wrong_conversion":
        data["latency_ms"] = 2.0
    elif mutation == "fake_missing":
        data["elapsed_ns"] = None
    elif mutation == "wrong_kind":
        data["measurement"] = "not_measured"
    else:
        data["input_tokens"] = 0
    with pytest.raises(ValueError):
        LatencyMetrics.model_validate(data)


@pytest.mark.parametrize("status", ["completed", "error", "timeout"])
def test_terminal_execution_requires_measured_time(status):
    with pytest.raises(ValueError):
        row(status)


@pytest.mark.parametrize("status", ["running", "not_run"])
def test_pending_rows_do_not_invent_time(status):
    with pytest.raises(ValueError):
        row(status, 0)


@pytest.mark.parametrize(
    "outcome",
    [
        "completed",
        "case_timeout",
        "cleanup_failed",
        "user_interrupted",
        "worker_start_failed",
    ],
)
def test_timer_surrounds_entire_base_case(tmp_path, monkeypatch, outcome):
    case = runner.datasets.load_dataset().cases[0]
    ticks = iter([10_000_000, 2_510_000_000])

    def execute(command, directory, timeout):
        if outcome == "completed":
            return fixtures.fake_worker(command, directory, timeout)
        return dict(
            code=None,
            error=outcome,
            cleanup=False if outcome == "cleanup_failed" else True,
        )

    monkeypatch.setattr(base, "run_process", execute)
    result = runner.timed_execute(
        case, tmp_path / "case", 60, clock=lambda: next(ticks)
    )
    assert (
        result.metrics.elapsed_ns == 2_500_000_000
        and result.metrics.latency_ms == 2500.0
    )
    assert result.metrics.measurement == (
        "complete_case" if outcome == "completed" else "partial_case"
    )
    assert (
        runner.datasets.read_json(tmp_path / "case/result.json") == result.model_dump()
    )


def test_keyboard_interrupt_keeps_partial_clock(tmp_path, monkeypatch):
    case = runner.datasets.load_dataset().cases[0]

    def stop(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(base, "execute_case", stop)
    ticks = iter([100, 200])
    result = runner.timed_execute(
        case, tmp_path / "case", 60, clock=lambda: next(ticks)
    )
    assert result.execution_status == "interrupted" and result.metrics.elapsed_ns == 100


def test_backwards_clock_rejected(tmp_path, monkeypatch):
    case = runner.datasets.load_dataset().cases[0]
    monkeypatch.setattr(base, "run_process", fixtures.fake_worker)
    ticks = iter([20, 10])
    with pytest.raises(ValueError):
        runner.timed_execute(case, tmp_path / "case", 60, clock=lambda: next(ticks))


@pytest.fixture
def prepared(monkeypatch):
    dataset = runner.datasets.load_dataset()
    agent = runner.datasets.AgentSpec.model_validate(
        runner.datasets.read_json(runner.datasets.AGENT)
    )
    monkeypatch.setattr(
        base,
        "prepare",
        lambda _d, _a, s: (
            runner.datasets.make_plan(dataset, agent, s),
            {"status": "passed"},
            {},
        ),
    )
    monkeypatch.setattr(base, "run_process", fixtures.fake_worker)


def test_full_orchestration_and_read_only_audit(tmp_path, prepared, monkeypatch):
    out = tmp_path / "run"
    report = runner.run(out, suite="smoke")
    assert (
        report["run_status"] == "completed"
        and report["latency_summary"]["measured_cases"] == 4
    )
    assert all(
        r["metrics"]["elapsed_ns"] > 0 and r["metrics"]["input_tokens"] is None
        for r in report["rows"]
    )
    assert report["summary"]["success_rate"] is None

    def forbidden(*args, **kwargs):
        raise AssertionError("inspect executed")

    monkeypatch.setattr(base.subprocess, "Popen", forbidden)
    assert runner.inspect(out)["status"] == "evidence_consistent"
    with pytest.raises(FileExistsError):
        runner.run(out)


@pytest.mark.parametrize(
    "mutation", ["summary", "sample_count", "row_duration", "artifact"]
)
def test_tampering_detected(tmp_path, prepared, mutation):
    out = tmp_path / "run"
    report = runner.run(out, suite="smoke")
    if mutation == "summary":
        report["latency_summary"]["by_execution_status"]["completed"]["p95_ms"] = (
            999999.0
        )
    elif mutation == "sample_count":
        report["latency_summary"]["measured_cases"] = 12
    elif mutation == "row_duration":
        report["rows"][0]["metrics"]["elapsed_ns"] += 1000000000
    else:
        (out / "cases/monthly_normal/artifacts/events.json").write_text(
            "tampered", encoding="utf-8"
        )
    base.atomic_save(out / "report.json", report)
    with pytest.raises(ValueError):
        runner.inspect(out)


def test_old_report_remains_unmeasured_and_uses_old_inspector():
    raw = runner.datasets.read_json(runner.ROOT / "docs/evidence/day87/execution.json")
    assert all(r["metrics"]["latency_ms"] is None for r in raw["rows"])
    with pytest.raises(ValueError):
        TimedReport.model_validate(copy.deepcopy(raw))
