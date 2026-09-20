"""Business-contract acceptance tests, including hostile and inconsistent inputs."""

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sales_contract import SalesReport, ScenarioInput
from scenario_rules import assess, validate_report

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
BY_ID = {case["id"]: case for case in CASES}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Scenario validation must stay offline")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_authored_acceptance_cases(case):
    source = ScenarioInput.model_validate(case["input"])
    expected = SalesReport.model_validate(case["expected"])
    assert assess(source) == expected
    validate_report(source, expected)


def change(data, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        data = data[int(part)] if isinstance(data, list) else data[part]
    last = int(parts[-1]) if isinstance(data, list) else parts[-1]
    data[last] = value


@pytest.mark.parametrize(
    "path,value",
    [
        ("request.period_start", "2026-02-30"),
        ("request.period_start", "2026-09-21"),
        ("request.period_start", "2026-08-01"),
        ("request.period_start", 20260914),
        ("request.period_end", "2026-9-20"),
        ("request.customer_ids", []),
        ("request.customer_ids", ["C-001", "C-001"]),
        ("request.customer_ids", [f"C-{i}" for i in range(21)]),
        ("request.customer_ids", ["C-001"]),
        ("request.customer_ids", ["../other"]),
        ("request.timezone", "UTC"),
        ("request.objective", "send_notifications"),
        ("request.send", True),
        ("data_source", "live_crm"),
        ("snapshots.0.records.0.created_at", "2026-09-16T02:00:00"),
        ("snapshots.0.records.0.created_at", "2026-02-30T02:00:00Z"),
        ("snapshots.0.records.0.customer_id", "other-customer"),
        ("snapshots.0.records.0.followup_id", "F-001"),
        ("snapshots.0.records.0.priority", "urgent"),
        ("snapshots.0.records.0.priority", True),
        ("snapshots.0.records.0.risk_flags", ["delivery_commitment"]),
        ("snapshots.0.records.0.missing_information", [" "]),
        ("snapshots.0.fetch_status", "error"),
        ("snapshots.0.error_code", "timeout"),
    ],
)
def test_rejects_invalid_or_unsafe_scope(path, value):
    data = copy.deepcopy(BY_ID["normal"]["input"])
    change(data, path, value)
    with pytest.raises(ValidationError):
        ScenarioInput.model_validate(data)


def test_no_fetch_snapshot_is_allowed_before_clarification():
    data = copy.deepcopy(BY_ID["normal"]["input"])
    data["request"]["period_start"] = None
    with pytest.raises(ValidationError, match="clarify_request_before_fetching"):
        ScenarioInput.model_validate(data)


def test_duplicate_snapshot_is_rejected():
    data = copy.deepcopy(BY_ID["normal"]["input"])
    data["snapshots"].append(copy.deepcopy(data["snapshots"][0]))
    with pytest.raises(ValidationError, match="duplicate_snapshot"):
        ScenarioInput.model_validate(data)


@pytest.mark.parametrize(
    "case,path,value",
    [
        ("normal", "recommendations.0.evidence_ids", ["fabricated-source"]),
        ("normal", "scope.period_start", "2026-09-15"),
        ("normal", "recommendations.0.customer_id", "unrequested-customer"),
        ("normal", "recommendations.0.evidence_ids", ["F-002"]),
        ("normal", "recommendations.0.evidence_ids", ["F-001", "F-001"]),
        ("normal", "recommendations.0.suggested_action", "maintain_followup"),
        ("normal", "recommendations", []),
        ("partial-query-failure", "status", "completed"),
        ("partial-query-failure", "gaps", []),
        ("pending-review", "recommendations.0.risk_flags", []),
        ("missing-information", "recommendations.0.missing_information", []),
        ("missing-input", "missing_fields", []),
    ],
)
def test_shape_valid_report_cannot_forge_business_success(case, path, value):
    source = ScenarioInput.model_validate(BY_ID[case]["input"])
    data = copy.deepcopy(BY_ID[case]["expected"])
    change(data, path, value)
    report = SalesReport.model_validate(data)
    with pytest.raises(ValueError, match="report_does_not_match_evidence_rules"):
        validate_report(source, report)


@pytest.mark.parametrize(
    "field,value",
    [
        ("business_actions_executed", True),
        ("model_requests", 1),
        ("execution_mode", "live"),
    ],
)
def test_report_cannot_claim_real_execution(field, value):
    data = copy.deepcopy(BY_ID["normal"]["expected"])
    data[field] = value
    with pytest.raises(ValidationError):
        SalesReport.model_validate(data)


def test_input_order_does_not_change_result_and_input_is_not_mutated():
    data = copy.deepcopy(BY_ID["normal"]["input"])
    original = copy.deepcopy(data)
    expected = assess(ScenarioInput.model_validate(data))
    data["snapshots"].reverse()
    data["request"]["customer_ids"].reverse()
    assert assess(ScenarioInput.model_validate(data)) == expected
    assert BY_ID["normal"]["input"] == original


def test_equivalent_timezone_timestamps_trigger_tie_conflict():
    data = copy.deepcopy(BY_ID["conflicting-priority"]["input"])
    data["snapshots"][0]["records"][1]["created_at"] = "2026-09-16T10:00:00+08:00"
    assert (
        assess(ScenarioInput.model_validate(data)).gaps[0].reason
        == "conflicting_priority"
    )


def test_cli_checks_all_cases_and_unknown_case_fails():
    for args, code in [(["--check-all"], 0), (["--case", "unknown"], 1)]:
        result = subprocess.run(
            [sys.executable, "-B", str(HERE / "check_scenario.py"), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        assert result.returncode == code, result.stderr
        value = json.loads(result.stdout)
        if code == 0:
            assert len(value["cases"]) == 13
            assert value["validation"] == "passed"
        else:
            assert value["error"] == "unknown_case"
