"""Independent rule mutations, denominator behavior and offline evidence integrity."""

import json
import socket
import sqlite3
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day85.contracts import canonical_hash  # noqa: E402
from experiments.day86.dataset_tool import load_dataset, read_json  # noqa: E402
from experiments.day87 import runner as files  # noqa: E402
from experiments.day88.latency import TimedRow, aggregate  # noqa: E402
from experiments.day89.reporting import MeteredReport, fixture_usage  # noqa: E402
from experiments.day90 import runner  # noqa: E402
from experiments.day90.scoring import (  # noqa: E402
    Grade,
    Rule,
    ScoredReport,
    judge,
    summary,
)

HISTORY = ROOT / "docs/evidence/day89"
DATASET = load_dataset()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network_or_agent_forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(runner.usage, "run", forbidden)


def sample(case_id="monthly_normal"):
    case = next(c for c in DATASET.cases if c.case_id == case_id)
    source = MeteredReport.model_validate(read_json(HISTORY / "execution.json"))
    row = next(r for r in source.execution.rows if r.case_id == case_id)
    return (
        case,
        row.observed,
        read_json(HISTORY / "cases" / case_id / "generation.json"),
        read_json(HISTORY / "cases" / case_id / "events.json"),
    )


@pytest.mark.parametrize("case_id", [c.case_id for c in DATASET.cases])
def test_all_independent_gold_cases(case_id):
    grade = judge(*sample(case_id))
    assert grade.judgement == "passed" and not grade.failed_rules
    assert len(grade.checks) >= 25


@pytest.mark.parametrize(
    "mutation,rule",
    [
        ("amount", "final_answer"),
        ("citation", "criterion_has_citation"),
        ("receipt_amount", "criterion_total_yuan"),
        ("scope", "receipt_scope"),
        ("period", "receipt_period"),
        ("detail", "receipt_orders"),
        ("status", "business_status"),
        ("retry", "behavior_tool_retries"),
        ("send", "criterion_external_send"),
        ("approval", "criterion_approval_status"),
        ("proposal", "approval_body"),
        ("events", "logged_tool_attempts"),
    ],
    ids=lambda x: x,
)
def test_wrong_semantics_fail(mutation, rule):
    case, observed, trace, journal = sample()
    if mutation == "amount":
        observed = observed.model_copy(
            update={"answer": observed.answer.replace("3000.00", "2050.00")}
        )
    if mutation == "citation":
        observed = observed.model_copy(
            update={"answer": observed.answer.replace(observed.agent_run_id, "0" * 32)}
        )
    if mutation in {"receipt_amount", "scope", "period", "detail"}:
        message = next(
            m
            for m in trace["actual_model_inputs"][-1]["messages"]
            if m.get("role") == "tool"
        )
        receipt = json.loads(message["content"])
        if mutation == "receipt_amount":
            receipt["result"]["total_yuan"] = "2050.00"
        if mutation == "scope":
            receipt["arguments"]["customer_id"] = "C001"
        if mutation == "period":
            receipt["result"]["period"]["start"] = "2026-08-01"
        if mutation == "detail":
            receipt["result"]["orders"][0]["amount_cents"] = 1
        message["content"] = json.dumps(receipt)
    if mutation == "status":
        observed = observed.model_copy(update={"business_status": "no_data"})
    if mutation == "retry":
        observed = observed.model_copy(update={"tool_retries": 1})
    if mutation == "send":
        observed = observed.model_copy(update={"external_send": True})
    if mutation == "approval":
        observed = observed.model_copy(update={"approval_status": "approved"})
    if mutation == "proposal":
        trace["approval"]["proposal"]["body"] = "invented report"
    if mutation == "events":
        journal["events"] = [e for e in journal["events"] if e["kind"] != "tool_call"]
    result = judge(case, observed, trace, journal)
    assert result.judgement == "failed"
    assert rule in result.failed_rules


def test_duplicate_receipt_keys_rejected():
    args = sample()
    m = next(
        m
        for m in args[2]["actual_model_inputs"][-1]["messages"]
        if m.get("role") == "tool"
    )
    m["content"] = '{"receipt_id":"a","receipt_id":"b"}'
    with pytest.raises(ValueError, match="duplicate_json_key"):
        judge(*args)


def test_boolean_is_not_integer_rule():
    with pytest.raises(ValueError):
        Rule(rule_id="strict", expected=1, actual=True, passed=True)


def grade_row(kind):
    reason = {"error": "execution_error", "not_evaluated": "execution_incomplete"}.get(
        kind
    )
    checks = (
        []
        if reason
        else [
            Rule(
                rule_id="answer",
                expected=1,
                actual=1 if kind == "passed" else 2,
                passed=kind == "passed",
            )
        ]
    )
    return Grade(
        case_id="case",
        category="normal",
        judgement=kind,
        reason=reason,
        checks=checks,
        failed_rules=["answer"] if kind == "failed" else [],
    )


def test_errors_remain_in_denominator():
    result = summary([grade_row("passed"), grade_row("failed"), grade_row("error")])
    assert result["denominator"] == 3 and result["numerator"] == 1
    assert result["success_rate_percent"] == 33.33


@pytest.mark.parametrize(
    "kinds", [[], ["not_evaluated"], ["passed", "error", "not_evaluated"]]
)
def test_incomplete_has_no_final_rate(kinds):
    result = summary([grade_row(k) for k in kinds])
    assert result["success_rate"] is result["success_rate_percent"] is None


def persist(root, data):
    execution = data["execution"]
    rows = [TimedRow.model_validate(r) for r in execution["rows"]]
    execution["summary"] = files.summarize(execution["rows"])
    execution["latency_summary"] = aggregate(rows)
    execution["plan_sha256"] = canonical_hash(execution["plan"])
    data["execution_sha256"] = canonical_hash(execution)
    from experiments.day88.latency import TimedReport

    data["usage"] = fixture_usage(TimedReport.model_validate(execution))
    files.atomic_save(root / "execution/report.json", execution)
    files.atomic_save(root / "report.json", data)


@pytest.fixture
def evidence_tree(tmp_path):
    """Reconstruct small evidence DBs from immutable historical JSON; never calls Agent."""
    root = tmp_path / "source"
    data = read_json(HISTORY / "execution.json")
    for row in data["execution"]["rows"]:
        case, observed, trace, journal = sample(row["case_id"])
        directory = root / "execution/cases" / case.case_id
        artifacts = directory / "artifacts"
        artifacts.mkdir(parents=True)
        files.atomic_save(artifacts / "generation.json", trace)
        files.atomic_save(artifacts / "events.json", journal)
        files.atomic_save(
            directory / "worker-result.json",
            dict(
                protocol="day87-worker-v1",
                case_id=case.case_id,
                case=case.input.case,
                scenario=case.input.scenario,
                observations=observed.model_dump(),
            ),
        )
        with sqlite3.connect(artifacts / "fictional.sqlite") as db:
            db.execute(
                "CREATE TABLE sales_orders(order_id,customer_id,order_date,amount_cents,status)"
            )
            for order in read_json(ROOT / "experiments/day65/sales-data.json")[
                "orders"
            ]:
                db.execute(
                    "INSERT INTO sales_orders VALUES(?,?,?,?,?)",
                    tuple(
                        order[k]
                        for k in [
                            "order_id",
                            "customer_id",
                            "order_date",
                            "amount_cents",
                            "status",
                        ]
                    ),
                )
        with sqlite3.connect(artifacts / "tasks.sqlite") as db:
            db.execute(
                "CREATE TABLE tasks(task_id,case_name,mode,status,created_at,finished_at)"
            )
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?)",
                tuple(
                    journal["task"][k]
                    for k in [
                        "task_id",
                        "case_name",
                        "mode",
                        "status",
                        "created_at",
                        "finished_at",
                    ]
                ),
            )
            db.execute("CREATE TABLE events(task_id,seq,kind,at,elapsed_ms,payload)")
            for event in journal["events"]:
                db.execute(
                    "INSERT INTO events VALUES(?,?,?,?,?,?)",
                    (
                        observed.task_id,
                        event["seq"],
                        event["kind"],
                        event["at"],
                        event["elapsed_ms"],
                        json.dumps(event["payload"]),
                    ),
                )
        if trace["approval"]:
            a = trace["approval"]
            with sqlite3.connect(artifacts / "approvals.sqlite") as db:
                db.execute("CREATE TABLE simulated_outbox(approval_id)")
                db.execute(
                    "CREATE TABLE approvals(approval_id,source_task_id,status,proposal,digest)"
                )
                db.execute(
                    "INSERT INTO approvals VALUES(?,?,?,?,?)",
                    (
                        a["approval_id"],
                        observed.task_id,
                        a["status"],
                        json.dumps(a["proposal"]),
                        a["digest"],
                    ),
                )
        row["artifacts"] = files.inventory(directory)
        files.atomic_save(directory / "result.json", row)
    persist(root, data)
    return root, data


def test_grade_inspect_readonly_and_preserves_metrics(evidence_tree, tmp_path):
    root, data = evidence_tree
    before = files.inventory(root)
    report = runner.grade(root, tmp_path / "score")
    assert report.summary["success_rate"] == 1 and report.full_dataset_evaluated
    assert report.source.model_dump() == data
    assert (
        runner.inspect(root, tmp_path / "score/report.json")["agent_executed"] is False
    )
    assert before == files.inventory(root)
    with pytest.raises(FileExistsError):
        runner.grade(root, tmp_path / "score")


@pytest.mark.parametrize(
    "damage", ["missing", "json", "rehash_db", "rehash_worker", "rehash_trace"]
)
def test_evidence_damage_counts_error(evidence_tree, damage):
    root, data = evidence_tree
    directory = root / "execution/cases/monthly_normal"
    if damage == "missing":
        (directory / "artifacts/generation.json").unlink()
    elif damage == "json":
        (directory / "artifacts/generation.json").write_text("{", encoding="utf-8")
    elif damage == "rehash_db":
        with sqlite3.connect(directory / "artifacts/fictional.sqlite") as db:
            db.execute("UPDATE sales_orders SET amount_cents=1")
    elif damage == "rehash_worker":
        worker = read_json(directory / "worker-result.json")
        worker["case_id"] = "customer_normal"
        files.atomic_save(directory / "worker-result.json", worker)
    else:
        trace = read_json(directory / "artifacts/generation.json")
        trace["generation"]["answer"] = "wrong"
        files.atomic_save(directory / "artifacts/generation.json", trace)
    if damage.startswith("rehash"):
        row = data["execution"]["rows"][0]
        row["artifacts"] = files.inventory(directory)
        files.atomic_save(directory / "result.json", row)
        persist(root, data)
    report = runner.calculate(root)
    assert report.results[0].reason == "evidence_invalid"
    assert report.summary["errors"] == 1 and report.summary["denominator"] == 12
    assert report.summary["success_rate_percent"] == 91.67


@pytest.mark.parametrize(
    "status", ["error", "timeout", "not_run", "running", "interrupted"]
)
def test_execution_status_denominator(evidence_tree, status):
    root, data = evidence_tree
    row = data["execution"]["rows"][0]
    row.update(
        execution_status=status,
        observed=None,
        worker_exit_code=None,
        artifacts={},
        error={
            "error": "worker_start_failed",
            "timeout": "case_timeout",
            "interrupted": "user_interrupted",
        }.get(status),
    )
    row["metrics"].update(measurement="partial_case")
    if status in {"not_run", "running", "interrupted"}:
        from experiments.day88.latency import LatencyMetrics

        row["metrics"] = LatencyMetrics().model_dump()
    data["execution"]["run_status"] = (
        "completed_with_errors"
        if status in {"error", "timeout"}
        else "running"
        if status == "running"
        else "interrupted"
    )
    persist(root, data)
    report = runner.calculate(root)
    assert report.summary["denominator"] == 12
    if status in {"error", "timeout"}:
        assert report.summary["success_rate_percent"] == 91.67
        assert report.results[0].reason == "execution_error"
    else:
        assert (
            report.summary["success_rate"] is None and not report.full_dataset_evaluated
        )


def test_smoke_not_full_dataset(evidence_tree):
    root, data = evidence_tree
    execution = data["execution"]
    execution["rows"] = execution["rows"][:4]
    plan = execution["plan"]
    plan["suite"] = "smoke"
    plan["rows"] = plan["rows"][:4]
    plan["summary"].update(total_cases=4, not_run=4)
    persist(root, data)
    report = runner.calculate(root)
    assert report.summary["denominator"] == 4 and report.summary["success_rate"] == 1
    assert report.full_dataset_evaluated is False


@pytest.mark.parametrize(
    "damage", ["summary", "grade", "category", "coverage", "source"]
)
def test_claimed_scoring_report_tampering_rejected(evidence_tree, damage):
    root, _ = evidence_tree
    report = runner.calculate(root).model_dump()
    if damage == "summary":
        report["summary"]["passed"] = 1
    if damage == "grade":
        report["results"][0]["checks"][0]["passed"] = False
    if damage == "category":
        report["results"][0]["category"] = "fallback"
    if damage == "coverage":
        report["results"].pop()
    if damage == "source":
        report["source_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        ScoredReport.model_validate(report)


def test_forged_rule_list_fails_reinspection(evidence_tree, tmp_path):
    root, _ = evidence_tree
    report = runner.calculate(root).model_dump()
    report["results"][0]["checks"] = report["results"][0]["checks"][:1]
    files.atomic_save(tmp_path / "forged.json", report)
    with pytest.raises(ValueError):
        runner.inspect(root, tmp_path / "forged.json")


def test_altered_dataset_rejected_even_with_rehash(evidence_tree):
    root, data = evidence_tree
    dataset = data["execution"]["plan"]["dataset"]
    dataset["cases"][0]["task"] += " changed"
    data["execution"]["plan"]["dataset_sha256"] = canonical_hash(dataset)
    persist(root, data)
    with pytest.raises(ValueError):
        runner.calculate(root)


def test_duplicate_rows_rejected(evidence_tree):
    root, data = evidence_tree
    data["execution"]["rows"][1] = deepcopy(data["execution"]["rows"][0])
    files.atomic_save(root / "report.json", data)
    with pytest.raises(ValueError):
        runner.calculate(root)


def test_cli_reports_failure_without_overwrite(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "marker").write_text("keep")
    assert (
        runner.main(
            [
                "grade",
                "--input-dir",
                str(tmp_path / "missing"),
                "--output-dir",
                str(output),
            ]
        )
        == 1
    )
    assert (output / "marker").read_text() == "keep"


def test_cli_nonpassing_result_is_saved_with_nonzero_exit(evidence_tree, tmp_path):
    root, _ = evidence_tree
    (root / "execution/cases/monthly_normal/artifacts/events.json").unlink()
    output = tmp_path / "score"
    assert (
        runner.main(["grade", "--input-dir", str(root), "--output-dir", str(output)])
        == 1
    )
    assert read_json(output / "report.json")["summary"]["errors"] == 1


def test_artifact_path_traversal_rejected(evidence_tree):
    root, data = evidence_tree
    row = data["execution"]["rows"][0]
    row["artifacts"]["../../outside"] = "0" * 64
    files.atomic_save(root / "execution/cases/monthly_normal/result.json", row)
    persist(root, data)
    assert runner.calculate(root).results[0].reason == "evidence_invalid"


def test_false_incomplete_reason_rejected():
    with pytest.raises(ValueError):
        Grade(
            case_id="case",
            category="normal",
            judgement="error",
            reason="execution_incomplete",
            checks=[],
            failed_rules=[],
        )
