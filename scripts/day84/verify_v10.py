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

from v10_gate import MANIFEST, ROOT, digest, validate

RELEASE_TESTS = 44
SUITES = (
    ("planner", "planner", 49, ["experiments/day59/test_task_planner.py"]),
    (
        "core",
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
    ("enterprise", "runtime", 259, [f"experiments/day{d}" for d in range(78, 83)]),
    ("release", "runtime", RELEASE_TESTS, ["scripts/day84/test_v10_release.py"]),
)


def junit_counts(path):
    tree = ET.parse(path).getroot()
    if tree.tag not in {"testsuite", "testsuites"}:
        raise ValueError("unsupported_junit_structure")
    suites = [tree] if tree.tag == "testsuite" else list(tree.findall("testsuite"))
    if not suites or any(s.findall("testsuite") for s in suites):
        raise ValueError("unsupported_junit_structure")
    total = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    seen = set()
    for suite in suites:
        counts = {k: int(suite.attrib[k]) for k in total}
        cases = suite.findall("testcase")
        observed = {
            "tests": len(cases),
            **{
                k: sum(c.find(tag) is not None for c in cases)
                for k, tag in (
                    ("failures", "failure"),
                    ("errors", "error"),
                    ("skipped", "skipped"),
                )
            },
        }
        if counts != observed:
            raise ValueError("inconsistent_junit_counts")
        for case in cases:
            identity = (case.attrib.get("classname"), case.attrib.get("name"))
            if not all(identity) or identity in seen:
                raise ValueError("missing_or_duplicate_test_identity")
            seen.add(identity)
        for key in total:
            total[key] += counts[key]
    return {**total, "test_ids": sorted(seen)}


def require_passed(counts, expected):
    if expected <= 0 or {
        k: counts[k] for k in ("tests", "failures", "errors", "skipped")
    } != dict(tests=expected, failures=0, errors=0, skipped=0):
        raise ValueError("suite_did_not_fully_pass")


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
        seen_tests = set()
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
                    timeout=900,
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
            identities = {tuple(item) for item in counts.pop("test_ids")}
            if seen_tests.intersection(identities):
                raise ValueError("overlapping_test_suites")
            seen_tests.update(identities)
            result["suites"].append(
                {"suite": name, "environment": environment, **counts}
            )
            print(json.dumps(result["suites"][-1]), flush=True)
        result["integrity_after"] = validate(root)
        if before != digest(root / MANIFEST):
            raise ValueError("manifest_changed_during_verification")
        result.update(
            status="passed",
            total_tests=len(seen_tests),
            demo_video_status="deferred",
            prompt_quality_improvement="not_measured",
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
        args.output_dir or Path(tempfile.mkdtemp(prefix="agent-v10-")) / "verification"
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
