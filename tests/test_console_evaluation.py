"""Real saved fixture report normalization, corruption and visible scoring errors."""

import json
from pathlib import Path

import pytest

from backend.app.console.evaluation_task import normalize
from experiments.day90.scoring import Grade, summary, summary_groups
from backend.app.console.evaluation_task import execute_evaluation


def source():
    # Captured from a network-disabled Linux 12-case run on 2026-10-24.
    return json.loads(
        (Path(__file__).parent / "fixtures/console-evaluation-source.json").read_text(
            encoding="utf-8"
        )
    )


def job():
    return {"job_id": "a" * 32, "input": {"suite": "full"}}


def test_original_results_and_latency_share_report_values():
    raw = source()
    result = normalize(raw, job())
    assert result["summary"] == raw["summary"]
    assert result["summary"]["denominator"] == 12
    assert result["latency"] == raw["source"]["execution"]["latency_summary"]
    assert result["usage"] == raw["source"]["usage"]["summary"]
    assert result["usage"]["total_tokens"] is None
    assert result["usage"]["estimated_model_api_cost"] == "0"
    rejected = [c for c in result["cases"] if c["business_status"] == "rejected"]
    assert rejected and all(c["judgement"] == "passed" for c in rejected)


def error_report():
    raw = source()
    first = raw["results"][0]
    first.update(
        judgement="error", reason="evidence_invalid", checks=[], failed_rules=[]
    )
    grades = [Grade.model_validate(g) for g in raw["results"]]
    raw["summary"] = summary(grades)
    raw["by_category"] = summary_groups(grades)
    return raw


def test_scoring_error_is_visible_and_stays_in_denominator():
    result = normalize(error_report(), job())
    assert result["summary"]["errors"] == 1
    assert result["summary"]["passed"] == 11
    assert result["summary"]["denominator"] == 12
    assert result["cases"][0]["reason"] == "evidence_invalid"
    assert result["cases"][0]["execution_status"] == "completed"
    assert result["cases"][0]["judgement"] == "error"


@pytest.mark.parametrize("field", ["summary", "rows", "timing", "usage", "suite"])
def test_inconsistent_report_is_rejected(field):
    raw = source()
    if field == "summary":
        raw["summary"]["passed"] = 99
    elif field == "rows":
        raw["results"].pop()
    elif field == "timing":
        raw["source"]["execution"]["latency_summary"]["sum_case_elapsed_ms"] = 0
    elif field == "usage":
        raw["source"]["usage"]["summary"]["total_tokens"] = 0
    else:
        raw["source"]["execution"]["plan"]["suite"] = "smoke"
    with pytest.raises(ValueError):
        normalize(raw, job())


def test_missing_score_recovers_without_reexecuting_agent(tmp_path, monkeypatch):
    commands = []

    def fake_run(command, **_):
        commands.append(command)
        output = Path(command[command.index("--output-dir") + 1])
        if "run" in command:
            (output / "run").mkdir(parents=True)
            (output / "run/report.json").write_text("{}")
        else:
            assert "grade" in command and "--input-dir" in command
            output.mkdir()
            (output / "report.json").write_text(json.dumps(source()), encoding="utf-8")
        from types import SimpleNamespace

        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("backend.app.console.evaluation_task.subprocess.run", fake_run)
    execute_evaluation(tmp_path, job())
    assert len(commands) == 2
    assert sum("run" in c for c in commands) == 1
    result = json.loads((tmp_path / "web-result.json").read_text(encoding="utf-8"))
    assert result["grading_recovery_from_saved_evidence"]
    assert result["summary"]["selected"] == 12
