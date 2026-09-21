"""Run the two independent offline release suites and fail on skips or bad counts."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from check_release import ROOT, validate


def junit_counts(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        raise ValueError("missing_junit_suite")
    return {
        key: sum(int(s.get(key, "0")) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }


def require_passed(counts: dict, expected: int) -> None:
    if counts != {"tests": expected, "failures": 0, "errors": 0, "skipped": 0}:
        raise ValueError("suite_did_not_fully_pass")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-python", type=Path, default=ROOT / ".venv/Scripts/python.exe"
    )
    parser.add_argument(
        "--graph-python",
        type=Path,
        default=ROOT / "experiments/day60/.venv/Scripts/python.exe",
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        integrity = validate()
        if not args.api_python.is_file() or not args.graph_python.is_file():
            raise ValueError("prepare_both_python_environments_first")
        if args.output_dir is None:
            output = Path(tempfile.mkdtemp(prefix="agent-center-v01-"))
        else:
            output = args.output_dir.resolve()
            output.mkdir(parents=True, exist_ok=False)
        print(json.dumps({"status": "running", "output_dir": str(output)}), flush=True)
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        suites = [
            (
                "api",
                args.api_python,
                116,
                [
                    "experiments/day61/test_sales_scenario.py",
                    "experiments/day62/test_sales_prompt.py",
                ],
            ),
            (
                "graph",
                args.graph_python,
                86,
                [
                    "experiments/day58/test_langgraph_basics.py",
                    "experiments/day59/test_task_planner.py",
                    "experiments/day60/test_task_progress.py",
                ],
            ),
            ("release", args.api_python, 17, ["scripts/day63/test_release.py"]),
        ]
        results = []
        for name, python, expected, files in suites:
            report = output / f"{name}.xml"
            completed = subprocess.run(
                [
                    str(python.resolve()),
                    "-B",
                    "-m",
                    "pytest",
                    *files,
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    f"--junitxml={report}",
                    f"--basetemp={output / (name + '-temp')}",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
            )
            (output / f"{name}.txt").write_text(
                completed.stdout + completed.stderr, encoding="utf-8"
            )
            if completed.returncode != 0:
                raise ValueError(f"{name}_suite_failed")
            counts = junit_counts(report)
            require_passed(counts, expected)
            results.append({"suite": name, **counts})
            print(json.dumps(results[-1]), flush=True)
        result = {
            "status": "passed",
            "integrity": integrity,
            "suites": results,
            "total_tests": sum(r["tests"] for r in results),
            "new_model_requests": 0,
            "live_business_tools_executed": False,
        }
        (output / "verification.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "output_dir": str(output),
                    "total_tests": result["total_tests"],
                }
            )
        )
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired, ET.ParseError):
        print(
            json.dumps(
                {"status": "failed", "error": "offline_release_verification_failed"}
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
