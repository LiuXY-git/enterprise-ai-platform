"""Full business scenarios plus negative controls on the acceptance oracle."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sales_acceptance as acceptance  # noqa: E402

SPECS = acceptance.load_matrix()


@pytest.fixture(scope="module")
def suite(tmp_path_factory):
    output = tmp_path_factory.mktemp("day81") / "acceptance"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(acceptance.__file__)),
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=360,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed" and report["scenario_count"] == 15
    assert report["passed"] == 15 and report["failed"] == 0
    return output, report


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_complete_business_scenario(suite, spec):
    output, report = suite
    result = next(r for r in report["results"] if r["id"] == spec["id"])
    assert result["status"] == "passed"
    trace = json.loads((output / result["trace"]).read_text(encoding="utf-8"))
    assert trace["outcome"] == result and trace["scenario"] == spec
    assert result["generation_status"] == spec["expected"]["status"]
    assert result["simulated_effects"] == (
        0 if spec["action"] in {"none", "reject", "expire"} else 1
    )
    assert result["model_requests"] == 0


def normal_trace(suite):
    return json.loads(
        (suite[0] / "monthly_approve/trace.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "mutation,expected_error",
    [
        ("amount", "business_total_mismatch"),
        ("orders", "business_total_mismatch"),
        ("rows", "detail_count_mismatch"),
        ("scope", "query_scope_mismatch"),
        ("citation", "citation_mismatch"),
        ("source", "proposal_source_mismatch"),
        ("body", "proposal_content_mismatch"),
        ("premature", "execution_before_approval"),
        ("final_event", "result_log_mismatch"),
        ("network", "unsafe_generation"),
    ],
)
def test_business_oracle_rejects_wrong_observations(suite, mutation, expected_error):
    trace = normal_trace(suite)
    created = trace["commands"][0]["response"]
    replay = trace["commands"][1]["response"]
    result = created["generation"]
    receipt = next(e["payload"] for e in replay["events"] if e["kind"] == "tool_result")
    if mutation == "amount":
        receipt["total_yuan"] = "9999.00"
    elif mutation == "orders":
        receipt["order_count"] = 99
    elif mutation == "rows":
        receipt["rows_returned"] = 4
    elif mutation == "scope":
        call = next(
            e["payload"]
            for e in replay["events"]
            if e["kind"] == "tool_call" and e["payload"].get("phase") == "attempt"
        )
        call["arguments"]["customer_id"] = "C001"
    elif mutation == "citation":
        result["answer"] = result["answer"].replace(result["agent_run_id"], "c" * 32)
        replay["events"][-1]["payload"]["answer"] = result["answer"]
    elif mutation == "source":
        created["approval"]["proposal"]["source_task_id"] = "c" * 32
    elif mutation == "body":
        created["approval"]["proposal"]["body"] += "unreviewed change"
    elif mutation == "premature":
        created["approval"]["simulation_count"] = 1
    elif mutation == "final_event":
        replay["events"][-1]["payload"]["status"] = "failed"
    elif mutation == "network":
        result["model_requests"] = 2
    with pytest.raises(acceptance.AcceptanceError, match=expected_error):
        acceptance.check_generation(trace["scenario"], created, replay)


@pytest.mark.parametrize(
    "mutation,expected_error",
    [
        ("no_approval", "missing_unique_approval"),
        ("wrong_digest", "approved_content_mismatch"),
        ("too_many_effects", "simulated_effect_count_mismatch"),
        ("changed_content", "executed_content_mismatch"),
        ("external", "external_send_detected"),
    ],
)
def test_audit_oracle_rejects_false_success(suite, mutation, expected_error):
    audit = normal_trace(suite)["audit"]
    approval = next(e for e in audit["events"] if e["kind"] == "human_approved")
    if mutation == "no_approval":
        audit["events"].remove(approval)
    elif mutation == "wrong_digest":
        data = json.loads(approval["details"])
        data["digest"] = "0" * 64
        approval["details"] = json.dumps(data)
    elif mutation == "too_many_effects":
        audit["outbox"].append(copy.deepcopy(audit["outbox"][0]))
    elif mutation == "changed_content":
        audit["outbox"][0]["proposal"] = "{}"
    elif mutation == "external":
        event = next(e for e in audit["events"] if e["kind"] == "simulation_executed")
        event["details"] = json.dumps({"external_send": True})
    with pytest.raises(acceptance.AcceptanceError, match=expected_error):
        acceptance.check_audit(audit, 1)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "escape", "action", "empty", "bad_expectation"]
)
def test_matrix_rejects_invalid_scenarios(tmp_path, mutation):
    matrix = json.loads(acceptance.MATRIX.read_text(encoding="utf-8"))
    if mutation == "duplicate":
        matrix["scenarios"].append(copy.deepcopy(matrix["scenarios"][0]))
    elif mutation == "escape":
        matrix["scenarios"][0]["id"] = "../outside"
    elif mutation == "action":
        matrix["scenarios"][0]["action"] = "external_email"
    elif mutation == "empty":
        matrix["scenarios"] = []
    elif mutation == "bad_expectation":
        matrix["scenarios"][0]["expected"]["order_count"] = True
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.load_matrix(path)


def test_existing_output_is_never_overwritten(tmp_path):
    marker = tmp_path / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        acceptance.run_suite(tmp_path, SPECS[:1])
    assert marker.read_text(encoding="utf-8") == "keep"


def test_expected_rejection_is_a_passed_test_not_completed_business(suite):
    result = next(r for r in suite[1]["results"] if r["id"] == "invalid_report")
    assert result["status"] == "passed" and result["generation_status"] == "rejected"
    assert result["simulated_effects"] == 0


def test_failed_case_is_saved_and_suite_fails(tmp_path, monkeypatch):
    def failed(spec, directory):
        return {"id": spec["id"], "status": "failed", "error": "injected_mismatch"}

    monkeypatch.setattr(acceptance, "run_scenario", failed)
    report = acceptance.run_suite(tmp_path / "report", SPECS[:1])
    assert report["status"] == "failed" and report["failed"] == 1
    assert (
        json.loads((tmp_path / "report/report.json").read_text())["status"] == "failed"
    )


def test_cli_list_does_not_run_scenarios(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-B", str(Path(acceptance.__file__)), "--list"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert proc.returncode == 0 and len(json.loads(proc.stdout)) == 15
    assert list(tmp_path.iterdir()) == []
