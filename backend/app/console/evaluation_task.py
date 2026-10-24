"""Execute the original fixed evaluator and normalize its verified saved report."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def normalize(raw, job):
    from experiments.day90.scoring import ScoredReport

    report = ScoredReport.model_validate(raw).model_dump()
    source = report["source"]
    execution = source["execution"]
    plan = execution["plan"]
    if plan["suite"] != job["input"]["suite"]:
        raise ValueError("suite_mismatch")
    rows = {r["case_id"]: r for r in execution["rows"]}
    usage = {r["case_id"]: r for r in source["usage"]["rows"]}
    cases = []
    for grade in report["results"]:
        row = rows[grade["case_id"]]
        cases.append(
            {
                **grade,
                "execution_status": row["execution_status"],
                "business_status": (row["observed"] or {}).get("business_status"),
                "error": row["error"],
                "latency_ms": row["metrics"]["latency_ms"],
                "usage": usage[row["case_id"]],
                "observed": row["observed"],
            }
        )
    return {
        "schema_version": "web-evaluation-v1",
        "job_id": job["job_id"],
        "mode": "fixture",
        "external_send": False,
        "suite": plan["suite"],
        "dataset_id": plan["dataset"]["dataset_id"],
        "dataset_version": plan["dataset"]["dataset_version"],
        "agent_id": plan["agent"]["agent_id"],
        "source_ids": {"evaluation_job_id": job["job_id"]},
        "dataset_sha256": plan["dataset_sha256"],
        "agent_spec_sha256": plan["agent_spec_sha256"],
        "summary": report["summary"],
        "by_category": report["by_category"],
        "cases": cases,
        "full_dataset_evaluated": report["full_dataset_evaluated"],
        "execution_status": execution["run_status"],
        "latency": execution["latency_summary"],
        "usage": source["usage"]["summary"],
        "notice": "固定虚构场景规则评测；fixture Token 未知，模型 API 成本不包含本地计算。通过率不代表真实模型质量。",
    }


def execute_evaluation(path, job):
    destination = path / "evaluation"
    command = [
        sys.executable,
        "-B",
        "scripts/evaluate.py",
        "--stage",
        "90",
        "run",
        "--suite",
        job["input"]["suite"],
        "--timeout-seconds",
        "60",
        "--output-dir",
        str(destination),
    ]
    with (
        (path / "evaluation.stdout.log").open("wb") as stdout,
        (path / "evaluation.stderr.log").open("wb") as stderr,
    ):
        completed = subprocess.run(
            command, cwd=ROOT, check=False, stdout=stdout, stderr=stderr
        )
    if completed.returncode not in {0, 1}:
        raise ValueError("evaluation_interrupted")
    report_path = destination / "evaluation/report.json"
    grading_recovery = False
    # A missing scoring file is not permission to execute the Agent again.
    # Grade the already persisted evidence once in a fresh directory. The original
    # grader verifies evidence consistency and retains incomplete/error rows.
    if not report_path.exists() and (destination / "run/report.json").is_file():
        recovered = destination / "recovered-grading"
        with (
            (path / "grading-recovery.stdout.log").open("wb") as stdout,
            (path / "grading-recovery.stderr.log").open("wb") as stderr,
        ):
            recovery = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "scripts/evaluate.py",
                    "--stage",
                    "90",
                    "grade",
                    "--input-dir",
                    str(destination / "run"),
                    "--output-dir",
                    str(recovered),
                ],
                cwd=ROOT,
                check=False,
                stdout=stdout,
                stderr=stderr,
            )
        if recovery.returncode not in {0, 1}:
            raise ValueError("grading_recovery_failed")
        report_path = recovered / "report.json"
        grading_recovery = True
    raw = report_path.read_bytes()
    result = normalize(json.loads(raw), job)
    result["source_report_sha256"] = hashlib.sha256(raw).hexdigest()
    result["grading_recovery_from_saved_evidence"] = grading_recovery
    (path / "web-result.json").write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    path = parser.parse_args().output_dir.resolve()
    job = json.loads((path / "request.json").read_text(encoding="utf-8"))
    execute_evaluation(path, job)


if __name__ == "__main__":
    main()
