"""Run disjoint offline suites in the existing planner and MCP environments."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from release_gate import MANIFEST, ROOT, digest, load_module, validate

# Reuse the frozen v0.2 strict JUnit parser; it does not run its test suites on import.
old_verifier = load_module(ROOT / "scripts/day70/verify_v02.py", "v05_junit_helpers")
junit_counts = old_verifier.junit_counts
require_passed = old_verifier.require_passed
RELEASE_TESTS = 38
SUITES = (
    ("planner", "planner", 49, ["experiments/day59/test_task_planner.py"]),
    (
        "runtime",
        "runtime",
        369,
        [
            "experiments/day64",
            "experiments/day65/test_sales_sql.py",
            "experiments/day72/test_sales_mcp.py",
            "experiments/day73",
            "experiments/day75",
        ],
    ),
    ("release", "runtime", RELEASE_TESTS, ["scripts/day77/test_v05_release.py"]),
)


def save(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def verify(output, runtime_python, planner_python, root=ROOT):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "suites": [],
        "new_model_requests": 0,
        "remote_tag_or_release_checked": False,
    }
    try:
        result["integrity"] = validate(root)
        before = digest(root / MANIFEST)
        env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
        env.pop("PYTEST_ADDOPTS", None)
        interpreters = {
            "runtime": Path(runtime_python).resolve(),
            "planner": Path(planner_python).resolve(),
        }
        for path in interpreters.values():
            if not path.is_file():
                raise ValueError("missing_python_environment")
        for name, environment, expected, files in SUITES:
            report = output / f"{name}.xml"
            command = [
                str(interpreters[environment]),
                "-B",
                "-m",
                "pytest",
                *files,
                "-q",
                "-p",
                "no:cacheprovider",
                f"--junitxml={report}",
                f"--basetemp={output / (name + '-temp')}",
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=300,
                )
            except subprocess.TimeoutExpired as exc:
                captured = b"".join(
                    v.encode("utf-8") if isinstance(v, str) else v or b""
                    for v in (exc.stdout, exc.stderr)
                )
                (output / f"{name}.txt").write_bytes(captured)
                raise ValueError("suite_timeout:" + name) from None
            (output / f"{name}.txt").write_text(
                completed.stdout + completed.stderr, encoding="utf-8"
            )
            if completed.returncode != 0:
                raise ValueError("suite_failed:" + name)
            counts = junit_counts(report)
            require_passed(counts, expected)
            result["suites"].append(
                {"suite": name, "environment": environment, **counts}
            )
            print(json.dumps(result["suites"][-1]), flush=True)
        result["integrity_after"] = validate(root)
        if before != digest(root / MANIFEST):
            raise ValueError("manifest_changed_during_verification")
        result.update(
            status="passed",
            total_tests=sum(s["tests"] for s in result["suites"]),
            manifest_sha256=before,
            completed_at=datetime.now(UTC).isoformat(),
            interpreters={k: str(v) for k, v in interpreters.items()},
        )
        result["output_hashes"] = {
            p.name: digest(p)
            for p in sorted(output.iterdir())
            if p.suffix in (".xml", ".txt")
        }
        save(output / "verification.json", result)
        return result
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        result.update(status="failed", error=type(exc).__name__ + ":" + str(exc))
        save(output / "failure.json", result)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-python",
        type=Path,
        default=ROOT / "experiments/day73/.venv/Scripts/python.exe",
    )
    parser.add_argument(
        "--planner-python",
        type=Path,
        default=ROOT / "experiments/day59/.venv/Scripts/python.exe",
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output = (
        args.output_dir or Path(tempfile.mkdtemp(prefix="agent-v05-")) / "verification"
    )
    print(json.dumps({"output_dir": str(output)}), flush=True)
    try:
        result = verify(output, args.runtime_python, args.planner_python)
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError):
        print(
            json.dumps({"status": "failed", "output_dir": str(output)}), file=sys.stderr
        )
        return 1
    print(
        json.dumps(
            {
                "status": result["status"],
                "total_tests": result["total_tests"],
                "output_dir": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
