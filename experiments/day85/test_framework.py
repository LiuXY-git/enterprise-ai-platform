"""Contract boundaries and non-execution guarantees for Day 85."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import framework as fw  # noqa: E402
from contracts import AgentSpec, Dataset, EvaluationPlan, canonical_hash  # noqa: E402


def raw(name):
    return json.loads((fw.EXAMPLES / (name + ".json")).read_text(encoding="utf-8"))


def plan():
    return fw.make_plan(
        AgentSpec.model_validate(raw("agent")), Dataset.model_validate(raw("dataset"))
    )


@pytest.mark.parametrize("name,model", [("agent", AgentSpec), ("dataset", Dataset)])
def test_example_roundtrip(name, model):
    value = model.model_validate(raw(name))
    assert model.model_validate_json(value.model_dump_json()) == value


def test_plan_has_no_fabricated_metrics():
    report = plan()
    assert report.summary.total_cases == report.summary.not_run == 2
    assert report.summary.passed == report.summary.failed == report.summary.errors == 0
    assert report.summary.success_rate is None
    assert EvaluationPlan.model_validate_json(report.model_dump_json()) == report
    for row in report.rows:
        assert row.execution_status == "not_run" and row.judgement == "not_evaluated"
        assert row.observed_business_status is None
        assert all(
            value is None
            for key, value in row.metrics.model_dump().items()
            if key != "notice"
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "empty",
        "duplicate",
        "blank_task",
        "unknown_case",
        "unknown_scenario",
        "unsupported_pair",
        "extra_parameter",
        "unknown_rule",
        "duplicate_rule",
        "duplicate_field",
        "money_number",
        "money_format",
        "bool_order_count",
        "string_boolean",
        "send",
        "effects",
        "judgement_in_input",
        "too_many",
    ],
)
def test_dataset_rejects_invalid_contract(mutation):
    data = raw("dataset")
    case = data["cases"][0]
    rules = case["expected"]["criteria"]
    if mutation == "schema":
        data["schema_version"] = "1.0"
    elif mutation == "empty":
        data["cases"] = []
    elif mutation == "duplicate":
        data["cases"].append(copy.deepcopy(case))
    elif mutation == "blank_task":
        case["task"] = "   "
    elif mutation == "unknown_case":
        case["input"]["case"] = "arbitrary_goal"
    elif mutation == "unknown_scenario":
        case["input"]["scenario"] = "run_shell"
    elif mutation == "unsupported_pair":
        case["input"]["case"] = "clarification"
        case["input"]["scenario"] = "invalid_report"
    elif mutation == "extra_parameter":
        case["input"]["shell"] = "echo bad"
    elif mutation == "unknown_rule":
        rules[0]["operator"] = "eval"
    elif mutation == "duplicate_rule":
        rules.append(copy.deepcopy(rules[0]))
    elif mutation == "duplicate_field":
        extra = copy.deepcopy(rules[0])
        extra["criterion_id"] = "other"
        rules.append(extra)
    elif mutation == "money_number":
        rules[0]["expected"] = 3000.0
    elif mutation == "money_format":
        rules[0]["expected"] = "3000"
    elif mutation == "bool_order_count":
        rules[1]["expected"] = True
    elif mutation == "string_boolean":
        rules[3]["expected"] = "true"
    elif mutation == "send":
        rules[-1]["expected"] = True
    elif mutation == "effects":
        rules[-2]["expected"] = 1
    elif mutation == "judgement_in_input":
        case["passed"] = True
    else:
        data["cases"] = [{**case, "case_id": f"case_{i}"} for i in range(101)]
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


@pytest.mark.parametrize(
    "mutation",
    ["mode", "adapter", "source_missing", "source_extra", "digest", "commit", "secret"],
)
def test_agent_rejects_unsupported_configuration(mutation):
    data = raw("agent")
    if mutation == "mode":
        data["mode"] = "live"
    elif mutation == "adapter":
        data["adapter_id"] = "shell_command"
    elif mutation == "source_missing":
        data["source_sha256_lf"].pop(next(iter(data["source_sha256_lf"])))
    elif mutation == "source_extra":
        data["source_sha256_lf"][".env"] = "a" * 64
    elif mutation == "digest":
        data["source_sha256_lf"]["experiments/day82/candidate.md"] = "not-a-sha"
    elif mutation == "commit":
        data["declared_source_commit"] = "main"
    else:
        data["api_key"] = "secret-value"
    with pytest.raises(ValidationError):
        AgentSpec.model_validate(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "passed",
        "failed",
        "errors",
        "total",
        "row_missing",
        "row_duplicate",
        "row_order",
        "judgement",
        "business_status",
        "latency",
        "tokens",
        "cost",
        "success_rate",
        "agent_hash",
        "dataset_hash",
    ],
)
def test_report_rejects_false_completion_or_identity(mutation):
    data = plan().model_dump()
    if mutation in {"passed", "failed", "errors"}:
        data["summary"][mutation] = 1
    elif mutation == "total":
        data["summary"]["total_cases"] = 99
    elif mutation == "row_missing":
        data["rows"].pop()
    elif mutation == "row_duplicate":
        data["rows"][1] = copy.deepcopy(data["rows"][0])
    elif mutation == "row_order":
        data["rows"].reverse()
    elif mutation == "judgement":
        data["rows"][0]["judgement"] = "passed"
    elif mutation == "business_status":
        data["rows"][0]["observed_business_status"] = "completed"
    elif mutation == "latency":
        data["rows"][0]["metrics"]["latency_ms"] = 0
    elif mutation == "tokens":
        data["rows"][0]["metrics"]["input_tokens"] = 0
    elif mutation == "cost":
        data["rows"][0]["metrics"]["cost"] = 0
    elif mutation == "success_rate":
        data["summary"]["success_rate"] = 1.0
    elif mutation == "agent_hash":
        data["agent"]["agent_id"] = "changed"
    else:
        data["dataset"]["cases"][0]["task"] = "changed"
    with pytest.raises(ValidationError):
        EvaluationPlan.model_validate(data)


@pytest.mark.parametrize(
    "text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', "{bad", "[" * 2000]
)
def test_invalid_json_rejected(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises((ValueError, RecursionError)):
        fw.load_contract(path, Dataset)


def test_large_input_rejected_before_parse(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * (fw.MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="input_too_large"):
        fw.load_contract(path, Dataset)


@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_preview_checks_local_source_hashes(tmp_path, mutation):
    agent = AgentSpec.model_validate(raw("agent"))
    for name in agent.source_sha256_lf:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((fw.ROOT / name).read_bytes())
    target = tmp_path / "experiments/day82/candidate.md"
    if mutation == "missing":
        target.unlink()
    else:
        target.write_text("changed")
    with pytest.raises((OSError, ValueError)):
        fw.make_plan(agent, Dataset.model_validate(raw("dataset")), tmp_path)


def test_hash_is_independent_of_json_key_order():
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})
    assert canonical_hash({"a": 1}) != canonical_hash({"a": True})


def test_preview_preserves_existing_output(tmp_path):
    marker = tmp_path / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        fw.preview(fw.EXAMPLES / "agent.json", fw.EXAMPLES / "dataset.json", tmp_path)
    assert list(tmp_path.iterdir()) == [marker] and marker.read_text() == "keep"


def test_invalid_input_creates_no_report(tmp_path):
    invalid = tmp_path / "bad.json"
    invalid.write_text("{}")
    output = tmp_path / "not-created"
    with pytest.raises(ValidationError):
        fw.preview(fw.EXAMPLES / "agent.json", invalid, output)
    assert not output.exists()


def test_preview_never_launches_process_or_network(tmp_path, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        pytest.fail("preflight must not execute or connect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    output = tmp_path / "plan"
    fw.preview(fw.EXAMPLES / "agent.json", fw.EXAMPLES / "dataset.json", output)
    assert (
        fw.load_contract(output / "report.json", EvaluationPlan).execution_status
        == "not_run"
    )


def test_exported_structural_schemas_validate_examples(tmp_path):
    output = tmp_path / "schemas"
    fw.export_schemas(output)
    for name, value in [
        ("agent", raw("agent")),
        ("dataset", raw("dataset")),
        ("plan-report", plan().model_dump()),
    ]:
        schema = json.loads(
            (output / (name + ".schema.json")).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(value, schema)
    with pytest.raises(FileExistsError):
        fw.export_schemas(output)


def test_cli_preview_and_report_check(tmp_path):
    output = tmp_path / "cli"
    command = [sys.executable, "-B", str(Path(fw.__file__))]
    first = subprocess.run(
        [*command, "preview", "--output-dir", str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    result = json.loads(first.stdout)
    assert result["execution_status"] == "not_run" and result["agent_executed"] is False
    second = subprocess.run(
        [*command, "check", "--kind", "report", "--file", str(output / "report.json")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert (
        second.returncode == 0
        and json.loads(second.stdout)["status"] == "contract_valid"
    )


def test_cli_failure_does_not_echo_sensitive_input(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"api_key":"never-echo-this-value"}')
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(fw.__file__)),
            "check",
            "--kind",
            "agent",
            "--file",
            str(bad),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert result.returncode == 1
    assert "never-echo-this-value" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["agent_executed"] is False
