"""Reject misleading gold, unsupported coverage and fabricated preflight results."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.day86 import dataset_tool as tool  # noqa: E402
from experiments.day86.dataset_contracts import DatasetPlan, FormalDataset  # noqa: E402


def raw():
    return tool.read_json(tool.DATASET)


def test_independent_totals_and_scope():
    dataset = tool.load_dataset()
    reports = [c.golden_report for c in dataset.cases[:3]]
    assert [r.total_cents for r in reports] == [
        120000 + 85000 + 35000 + 60000,
        120000 + 35000,
        0,
    ]
    assert reports[0].displayed_order_ids == ["SO-001", "SO-002"]
    assert reports[0].total_cents != 120000 + 85000
    assert reports[1].matched_order_ids == ["SO-001", "SO-003"]
    assert reports[2].matched_order_ids == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_case",
        "duplicate_input",
        "duplicate_id",
        "smoke_duplicate",
        "smoke_order",
        "wrong_category",
        "wrong_status",
        "unsafe_send",
        "missing_rule",
        "bool_count",
        "wrong_budget",
        "wrong_stop",
        "fake_degraded",
        "scope",
        "wrong_total",
        "limit",
        "duplicate_order",
        "wrong_citation",
        "failure_gold",
        "unknown_source",
        "extra_field",
    ],
)
def test_rejects_bad_dataset(mutation):
    d = raw()
    c = d["cases"][0]
    rules = c["expected"]["criteria"]
    if mutation == "missing_case":
        d["cases"].pop()
    elif mutation == "duplicate_input":
        d["cases"][1]["input"] = copy.deepcopy(c["input"])
    elif mutation == "duplicate_id":
        d["cases"][1]["case_id"] = c["case_id"]
    elif mutation == "smoke_duplicate":
        d["smoke_case_ids"][1] = d["smoke_case_ids"][0]
    elif mutation == "smoke_order":
        d["smoke_case_ids"].reverse()
    elif mutation == "wrong_category":
        c["category"] = "no_data"
    elif mutation == "wrong_status":
        c["expected"]["business_status"] = "no_data"
    elif mutation == "unsafe_send":
        rules[-1]["expected"] = True
    elif mutation == "missing_rule":
        rules.pop()
    elif mutation == "bool_count":
        rules[1]["expected"] = True
    elif mutation == "wrong_budget":
        c["behavior"]["tool_attempts"] = 9
    elif mutation == "wrong_stop":
        c["behavior"]["stop_reason"] = "report_does_not_match_receipt"
    elif mutation == "fake_degraded":
        c["behavior"]["degraded"] = True
    elif mutation == "scope":
        c["golden_report"]["scope"]["month"] = 7
    elif mutation == "wrong_total":
        c["golden_report"]["total_cents"] = 205000
    elif mutation == "limit":
        c["golden_report"]["displayed_order_ids"].pop()
    elif mutation == "duplicate_order":
        c["golden_report"]["matched_order_ids"].append("SO-001")
    elif mutation == "wrong_citation":
        rules[3]["expected"] = False
    elif mutation == "failure_gold":
        d["cases"][-1]["golden_report"] = c["golden_report"]
    elif mutation == "unknown_source":
        d["source_sha256_lf"]["../secrets"] = "0" * 64
    else:
        c["input"]["command"] = "arbitrary"
    with pytest.raises(ValueError):
        FormalDataset.model_validate(d)


def test_coherent_but_wrong_gold_rejected_by_independent_oracle():
    d = raw()
    d["cases"][0]["golden_report"]["total_cents"] = 205000
    d["cases"][0]["expected"]["criteria"][0]["expected"] = "2050.00"
    parsed = FormalDataset.model_validate(d)
    with pytest.raises(ValueError, match="oracle_mismatch"):
        tool.verify_oracle(parsed)


def test_changed_source_rejected(tmp_path):
    dataset = tool.load_dataset()
    for name in dataset.source_sha256_lf:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((tool.ROOT / name).read_bytes())
    (tmp_path / "experiments/day65/sales-data.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="source_hash_mismatch"):
        tool.verify_oracle(dataset, tmp_path)


@pytest.mark.parametrize("suite,count", [("smoke", 4), ("full", 12)])
def test_plan_selection_unmeasured_and_schema(suite, count):
    dataset = tool.load_dataset()
    agent = tool.AgentSpec.model_validate(tool.read_json(tool.AGENT))
    plan = tool.make_plan(dataset, agent, suite)
    assert plan.summary.total_cases == plan.summary.not_run == count
    assert plan.summary.success_rate is None
    assert all(
        r.judgement == "not_evaluated" and r.metrics.cost is None for r in plan.rows
    )
    jsonschema.validate(plan.model_dump(), DatasetPlan.model_json_schema())
    jsonschema.validate(dataset.model_dump(), FormalDataset.model_json_schema())
    data = plan.model_dump()
    data["summary"]["passed"] = 1
    with pytest.raises(ValueError):
        DatasetPlan.model_validate(data)
    data = plan.model_dump()
    data["rows"].pop()
    with pytest.raises(ValueError):
        DatasetPlan.model_validate(data)


@pytest.mark.parametrize(
    "content",
    [
        '{"a":1,"a":2}',
        '{"n":NaN}',
        '{"n":Infinity}',
        pytest.param("x" * 1048577, id="oversize"),
    ],
)
def test_bad_json(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        tool.read_json(path)


def test_preflight_never_imports_or_executes_runtime(tmp_path, monkeypatch, capsys):
    import socket
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected execution")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    out = tmp_path / "plan"
    assert tool.main(["preview", "--output-dir", str(out)]) == 0
    before = hashlib.sha256((out / "report.json").read_bytes()).hexdigest()
    assert tool.main(["preview", "--output-dir", str(out)]) == 1
    assert hashlib.sha256((out / "report.json").read_bytes()).hexdigest() == before
    assert "prompt_lab" not in sys.modules
    assert "agent_executed" in capsys.readouterr().out


def test_cli_sanitizes_errors(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"secret": "must-not-echo"}), encoding="utf-8")
    assert tool.main(["check", "--dataset", str(path)]) == 1
    assert "must-not-echo" not in capsys.readouterr().out
