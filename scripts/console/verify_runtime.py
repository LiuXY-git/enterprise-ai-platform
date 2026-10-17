"""Prove existing fixture Agent and evaluator in a new isolated directory."""

import argparse
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    commands = [
        [
            sys.executable,
            "-B",
            "experiments/day82/prompt_lab.py",
            "prepare",
            "--case",
            "monthly",
            "--scenario",
            "normal",
            "--output-dir",
            str(output / "agent"),
        ],
        [
            sys.executable,
            "-B",
            "scripts/evaluate.py",
            "--stage",
            "90",
            "run",
            "--suite",
            "smoke",
            "--timeout-seconds",
            "60",
            "--output-dir",
            str(output / "evaluation"),
        ],
    ]
    try:
        for name, command in zip(("agent", "evaluation"), commands, strict=True):
            with (
                (output / f"{name}.stdout.log").open("w", encoding="utf-8") as stdout,
                (output / f"{name}.stderr.log").open("w", encoding="utf-8") as stderr,
            ):
                subprocess.run(
                    command,
                    cwd=ROOT,
                    stdout=stdout,
                    stderr=stderr,
                    check=True,
                    timeout=240,
                )
        generation = read(output / "agent/generation.json")
        if (
            generation["generation"]["status"] != "completed"
            or generation["external_send"]
        ):
            raise ValueError("agent_not_completed_or_external_send")
        if generation["approval"]["status"] != "pending":
            raise ValueError("approval_not_pending")
        with closing(sqlite3.connect(output / "agent/approvals.sqlite")) as db:
            effects = db.execute("SELECT COUNT(*) FROM simulated_outbox").fetchone()[0]
        if effects:
            raise ValueError("unexpected_simulated_send")
        report = read(output / "evaluation/evaluation/report.json")
        summary = report["summary"]
        if not (
            summary["selected"] == summary["passed"] == 4
            and summary["status"] == "complete"
            and not report["full_dataset_evaluated"]
        ):
            raise ValueError("evaluation_smoke_failed")
        result = {
            "status": "passed",
            "python": platform.python_version(),
            "platform": platform.system(),
            "mode": "fixture",
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("mcp", "httpx", "pydantic")
            },
            "agent_status": "completed",
            "approval_status": "pending",
            "simulated_sends": effects,
            "external_send": False,
            "evaluation": summary,
            "full_dataset_evaluated": False,
            "new_real_model_requests": 0,
        }
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        result = {"status": "failed", "notice": "Inspect the preserved proof logs."}
    (output / "verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
