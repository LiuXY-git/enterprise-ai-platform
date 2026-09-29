"""Execute fixture cases or grade existing evidence, with an explicit denominator."""

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day85.contracts import canonical_hash  # noqa: E402
from experiments.day86.dataset_tool import (  # noqa: E402
    load_dataset,
    read_json,
    reject_constant,
    unique_object,
    verify_hashes,
)
from experiments.day87 import runner as files  # noqa: E402
from experiments.day87.execution_contracts import WorkerResult  # noqa: E402
from experiments.day87.worker import collect  # noqa: E402
from experiments.day89 import runner as usage  # noqa: E402
from experiments.day89.reporting import MeteredReport  # noqa: E402
from experiments.day90.scoring import (  # noqa: E402
    Grade,
    ScoredReport,
    judge,
    summary,
    summary_groups,
)

HERE = Path(__file__).resolve().parent


def same(left, right):
    if canonical_hash(left) != canonical_hash(right):
        raise ValueError("evidence_mismatch")


def parse(text):
    return json.loads(
        text, object_pairs_hook=unique_object, parse_constant=reject_constant
    )


def database(path):
    return closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    )


def evidence(root, case, row):
    directory = files.contained(root, "execution/cases/" + case.case_id)
    same(read_json(files.contained(directory, "result.json")), row.model_dump())
    same(files.inventory(directory), row.artifacts)
    artifacts = files.contained(directory, "artifacts")
    trace = read_json(files.contained(artifacts, "generation.json"))
    journal = read_json(files.contained(artifacts, "events.json"))
    worker = WorkerResult.model_validate(
        read_json(files.contained(directory, "worker-result.json"))
    )
    same(
        [worker.case_id, worker.case, worker.scenario],
        [case.case_id, case.input.case, case.input.scenario],
    )
    same(worker.observations.model_dump(), row.observed.model_dump())
    same(collect(trace, journal, artifacts).model_dump(), row.observed.model_dump())
    generation = trace["generation"]
    same(
        journal["events"][-1]["payload"],
        {k: v for k, v in generation.items() if k != "task_id"},
    )
    same(
        trace["prompt"]["sha256_lf"],
        files.digest(ROOT / "experiments/day82/candidate.md", lf=True),
    )
    with database(files.contained(artifacts, "tasks.sqlite")) as db:
        db.row_factory = sqlite3.Row
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks")]
        same(tasks, [journal["task"]])
        events = [
            dict(r)
            for r in db.execute(
                "SELECT seq, kind, at, elapsed_ms, payload FROM events WHERE task_id=? ORDER BY seq",
                (row.observed.task_id,),
            )
        ]
        for event in events:
            event["payload"] = parse(event["payload"])
        same(events, journal["events"])
    with database(files.contained(artifacts, "fictional.sqlite")) as db:
        db.row_factory = sqlite3.Row
        orders = [
            dict(r)
            for r in db.execute(
                "SELECT order_id, customer_id, order_date, amount_cents, status FROM sales_orders ORDER BY order_id"
            )
        ]
        same(
            orders,
            sorted(
                read_json(ROOT / "experiments/day65/sales-data.json")["orders"],
                key=lambda r: r["order_id"],
            ),
        )
    approval = trace.get("approval")
    approval_path = files.contained(artifacts, "approvals.sqlite")
    if approval_path.exists():
        with database(approval_path) as db:
            records = db.execute(
                "SELECT approval_id, source_task_id, status, proposal, digest FROM approvals"
            ).fetchall()
            if approval is None:
                same(records, [])
            else:
                same(
                    [list(r[:3]) + [parse(r[3]), r[4]] for r in records],
                    [
                        [
                            approval["approval_id"],
                            row.observed.task_id,
                            approval["status"],
                            approval["proposal"],
                            approval["digest"],
                        ]
                    ],
                )
    elif approval is not None:
        raise ValueError("missing_approval_database")
    return trace, journal


def calculate(input_dir):
    root = Path(input_dir).resolve()
    source = MeteredReport.model_validate(
        read_json(files.contained(root, "report.json"))
    )
    same(
        read_json(files.contained(root, "execution/report.json")),
        source.execution.model_dump(),
    )
    # Never trust caller-supplied replacement gold just because it is self-consistent.
    same(source.execution.plan.dataset.model_dump(), load_dataset().model_dump())
    cases = {c.case_id: c for c in source.execution.plan.dataset.cases}
    results = []
    for row in source.execution.rows:
        case = cases[row.case_id]
        if row.execution_status in {"not_run", "running", "interrupted"}:
            result = Grade(
                case_id=row.case_id,
                category=case.category,
                judgement="not_evaluated",
                reason="execution_incomplete",
                checks=[],
                failed_rules=[],
            )
        elif row.execution_status != "completed":
            result = Grade(
                case_id=row.case_id,
                category=case.category,
                judgement="error",
                reason="execution_error",
                checks=[],
                failed_rules=[],
            )
        else:
            try:
                trace, journal = evidence(root, case, row)
                result = judge(case, row.observed, trace, journal)
            except (
                OSError,
                ValueError,
                TypeError,
                KeyError,
                IndexError,
                AttributeError,
                sqlite3.Error,
                RecursionError,
            ):
                result = Grade(
                    case_id=row.case_id,
                    category=case.category,
                    judgement="error",
                    reason="evidence_invalid",
                    checks=[],
                    failed_rules=[],
                )
        results.append(result)
    counts = summary(results)
    return ScoredReport(
        schema_version="day90-scoring-v1",
        report_kind="fixed_fixture_rule_evaluation",
        source=source,
        source_sha256=canonical_hash(source.model_dump()),
        scorer_source_sha256_lf={
            p.relative_to(ROOT).as_posix(): files.digest(p, lf=True)
            for p in HERE.glob("*.py")
            if not p.name.startswith("test_")
        },
        ruleset="day86-sales-fixture-rules-v1",
        results=results,
        summary=counts,
        by_category=summary_groups(results),
        full_dataset_evaluated=source.execution.plan.suite == "full"
        and len(results) == len(cases)
        and counts["not_evaluated"] == 0,
        grading_executes_agent=False,
    )


def grade(input_dir, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("existing_output")
    result = calculate(input_dir)
    output.mkdir(parents=True, exist_ok=False)
    files.atomic_save(output / "report.json", result.model_dump())
    return result


def run(output, *, suite="full", timeout=60):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("existing_output")
    usage.run(output / "run", suite=suite, timeout=timeout)
    return grade(output / "run", output / "evaluation")


def inspect(input_dir, report_path):
    report = ScoredReport.model_validate(read_json(report_path))
    verify_hashes(report.scorer_source_sha256_lf, ROOT)
    same(report.model_dump(), calculate(input_dir).model_dump())
    return dict(
        status="evidence_consistent", summary=report.summary, agent_executed=False
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--suite", choices=["smoke", "full"], default="full")
    execute.add_argument("--timeout-seconds", type=int, default=60)
    execute.add_argument("--output-dir", type=Path, required=True)
    score = sub.add_parser("grade")
    score.add_argument("--input-dir", type=Path, required=True)
    score.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("inspect")
    check.add_argument("--input-dir", type=Path, required=True)
    check.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect(args.input_dir, args.report)
            code = 0
        else:
            report = (
                run(args.output_dir, suite=args.suite, timeout=args.timeout_seconds)
                if args.command == "run"
                else grade(args.input_dir, args.output_dir)
            )
            result = dict(
                summary=report.summary,
                by_category=report.by_category,
                full_dataset_evaluated=report.full_dataset_evaluated,
            )
            code = (
                0
                if report.summary["passed"] == report.summary["selected"]
                and report.summary["status"] == "complete"
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
        files.subprocess.SubprocessError,
    ):
        print(
            json.dumps(
                dict(
                    status="failed",
                    error="scoring_input_io_or_execution_invalid",
                    notice="Keep existing evidence; use a new directory.",
                )
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
