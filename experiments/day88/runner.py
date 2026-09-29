"""Day 88 execution with measured case latency; reuses the Day 87 fixture adapter."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day85.contracts import canonical_hash  # noqa: E402
from experiments.day86 import dataset_tool as datasets  # noqa: E402
from experiments.day87 import runner as base  # noqa: E402
from experiments.day88.latency import (  # noqa: E402
    LatencyMetrics,
    TimedReport,
    TimedRow,
    aggregate,
    milliseconds,
)  # noqa: E402


def timed_execute(case, directory, timeout, *, clock=perf_counter_ns):
    started = clock()
    try:
        row = base.execute_case(case, directory, timeout).model_dump()
    except KeyboardInterrupt:
        row = dict(
            case_id=case.case_id,
            execution_status="interrupted",
            error="user_interrupted",
            artifacts=base.inventory(directory) if directory.exists() else {},
        )
    elapsed = clock() - started
    metrics = LatencyMetrics(
        elapsed_ns=elapsed,
        latency_ms=milliseconds(elapsed),
        measurement="complete_case"
        if row["execution_status"] == "completed"
        else "partial_case",
    )
    row["metrics"] = metrics.model_dump()
    result = TimedRow.model_validate(row)
    # Excluded from timing: this second write adds Day 88 timing metadata.
    directory.mkdir(exist_ok=True)
    base.atomic_save(directory / "result.json", result.model_dump())
    return result


def persist(output, report):
    report["summary"] = base.summarize(report["rows"])
    report["latency_summary"] = aggregate(
        [TimedRow.model_validate(r) for r in report["rows"]]
    )
    valid = TimedReport.model_validate(report)
    base.atomic_save(output / "report.json", valid.model_dump())


def run(
    output, *, dataset=datasets.DATASET, agent=datasets.AGENT, suite="full", timeout=60
):
    if (
        type(timeout) is not int
        or not 5 <= timeout <= 120
        or suite not in {"smoke", "full"}
    ):
        raise ValueError("invalid_runner_options")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("existing_run_directory")
    plan, frozen, hashes = base.prepare(dataset, agent, suite)
    for path in Path(__file__).parent.glob("*.py"):
        if not path.name.startswith("test_"):
            hashes[path.relative_to(ROOT).as_posix()] = base.digest(path, lf=True)
    report = dict(
        schema_version="day88-latency-v1",
        report_kind="execution_record_not_scored_evaluation",
        run_status="running",
        plan=plan.model_dump(),
        plan_sha256=canonical_hash(plan.model_dump()),
        timeout_seconds=timeout,
        execution_mode="fixture_model_real_local_mcp",
        rows=[
            TimedRow(case_id=r.case_id, execution_status="not_run").model_dump()
            for r in plan.rows
        ],
        source_sha256_lf=hashes,
        frozen_integrity=frozen,
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    persist(output, report)
    selected = {c.case_id: c for c in plan.dataset.cases}
    active = None
    try:
        for index, row in enumerate(report["rows"]):
            active = index
            row["execution_status"] = "running"
            persist(output, report)
            result = timed_execute(
                selected[row["case_id"]], output / "cases" / row["case_id"], timeout
            )
            report["rows"][index] = result.model_dump()
            persist(output, report)
            print(
                json.dumps(
                    dict(
                        case_id=result.case_id,
                        execution_status=result.execution_status,
                        latency_ms=result.metrics.latency_ms,
                    )
                ),
                flush=True,
            )
            if (
                result.execution_status == "interrupted"
                or result.error == "cleanup_failed"
            ):
                report["run_status"] = "interrupted"
                persist(output, report)
                return report
            active = None
        report["run_status"] = (
            "completed"
            if all(r["execution_status"] == "completed" for r in report["rows"])
            else "completed_with_errors"
        )
    except KeyboardInterrupt:
        if (
            active is not None
            and report["rows"][active]["execution_status"] == "running"
        ):
            row = TimedRow(
                case_id=report["rows"][active]["case_id"],
                execution_status="interrupted",
                error="user_interrupted",
            )
            directory = output / "cases" / row.case_id
            directory.mkdir(exist_ok=True)
            row.artifacts = base.inventory(directory)
            base.atomic_save(directory / "result.json", row.model_dump())
            report["rows"][active] = row.model_dump()
        report["run_status"] = "interrupted"
    persist(output, report)
    return report


def inspect(output):
    output = Path(output).resolve()
    report = TimedReport.model_validate(datasets.read_json(output / "report.json"))
    for row in report.rows:
        directory = base.contained(output, Path("cases") / row.case_id)
        if row.execution_status in {"not_run", "running"}:
            continue
        if (
            datasets.read_json(directory / "result.json") != row.model_dump()
            or base.inventory(directory) != row.artifacts
        ):
            raise ValueError("case_evidence_mismatch")
    return dict(
        status="evidence_consistent",
        run_status=report.run_status,
        summary=report.summary.model_dump(),
        latency_summary=report.latency_summary,
        agent_executed=False,
        judgement="not_evaluated",
        notice="local_fixture_observation_not_live_model_benchmark",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--dataset", type=Path, default=datasets.DATASET)
    execute.add_argument("--agent", type=Path, default=datasets.AGENT)
    execute.add_argument("--suite", choices=["smoke", "full"], default="full")
    execute.add_argument("--timeout-seconds", type=int, default=60)
    execute.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("inspect")
    check.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result, code = inspect(args.output_dir), 0
        else:
            report = run(
                args.output_dir,
                dataset=args.dataset,
                agent=args.agent,
                suite=args.suite,
                timeout=args.timeout_seconds,
            )
            result = {
                k: report[k] for k in ("run_status", "summary", "latency_summary")
            }
            code = (
                0
                if report["run_status"] == "completed"
                else 130
                if report["run_status"] == "interrupted"
                else 1
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print(
            json.dumps(
                dict(
                    status="failed",
                    error="latency_runner_input_io_or_preflight_failed",
                    notice="Keep existing evidence; use a new directory.",
                )
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
