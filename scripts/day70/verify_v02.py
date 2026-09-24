"""Run offline v0.2 tests in fresh directories; retain logs and reject skips."""

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from release_gate import MANIFEST, ROOT, digest, validate

RELEASE_TESTS = 40
SUITES = (
    (
        "tools",
        648,
        [
            *[f"experiments/day{d}" for d in range(64, 70)],
            "tests/test_retrieval_service.py",
        ],
    ),
    ("release", RELEASE_TESTS, ["scripts/day70/test_v02_release.py"]),
)


def junit_counts(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites or any(s.findall("testsuite") for s in suites):
        raise ValueError("unsupported_junit_structure")
    total = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
    for suite in suites:
        counts = {k: int(suite.attrib[k]) for k in total}
        cases = suite.findall("testcase")
        observed = {
            "tests": len(cases),
            **{
                key: sum(c.find(tag) is not None for c in cases)
                for key, tag in (
                    ("failures", "failure"),
                    ("errors", "error"),
                    ("skipped", "skipped"),
                )
            },
        }
        if counts != observed:
            raise ValueError("inconsistent_junit_counts")
        for key in total:
            total[key] += counts[key]
    return total


def require_passed(counts: dict, expected: int) -> None:
    if expected <= 0 or counts != {
        "tests": expected,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }:
        raise ValueError("suite_did_not_fully_pass")


def save(path: Path, result: dict) -> None:
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def verify(output: Path, python: Path, root: Path = ROOT) -> dict:
    # Caller must supply a new output path. Never delete an existing pytest temp tree.
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "suites": [],
        "new_model_requests": 0,
        "new_weather_requests": 0,
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
        for name, expected, files in SUITES:
            report = output / f"{name}.xml"
            try:
                completed = subprocess.run(
                    [
                        str(python),
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
            result["suites"].append({"suite": name, **counts})
            print(json.dumps(result["suites"][-1]), flush=True)
        result["integrity_after"] = validate(root)
        if before != digest(root / MANIFEST):
            raise ValueError("manifest_changed_during_verification")
        result.update(
            status="passed",
            total_tests=sum(s["tests"] for s in result["suites"]),
            manifest_sha256=before,
            completed_at=datetime.now(UTC).isoformat(),
        )
        result["environment"] = {
            "python": platform.python_version(),
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("pytest", "pydantic", "httpx", "chromadb", "onnxruntime")
            },
        }
        result["output_hashes"] = {
            p.name: digest(p)
            for p in sorted(output.iterdir())
            if p.suffix in {".xml", ".txt"}
        }
        save(output / "verification.json", result)
        return result
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        result.update(status="failed", error=type(exc).__name__ + ":" + str(exc))
        save(output / "failure.json", result)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.output_dir is None:
        parent = Path(tempfile.mkdtemp(prefix="agent-v02-"))
        output = parent / "verification"
    else:
        output = args.output_dir.resolve()
    print(json.dumps({"status": "running", "output_dir": str(output)}), flush=True)
    try:
        result = verify(output, Path(sys.executable).resolve())
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError):
        print(
            json.dumps({"status": "failed", "output_dir": str(output)}), file=sys.stderr
        )
        return 1
    print(
        json.dumps(
            {
                "status": "passed",
                "total_tests": result["total_tests"],
                "output_dir": str(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
