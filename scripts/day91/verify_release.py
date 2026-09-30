"""Offline release acceptance: unique tests, fresh full fixture run and reinspection."""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/day84"))
from experiments.day86.dataset_tool import read_json  # noqa: E402
from experiments.day87.runner import atomic_save, stop_tree  # noqa: E402
from experiments.day90 import runner as scoring  # noqa: E402
from scripts.day84.verify_v10 import junit_counts, require_passed  # noqa: E402
from scripts.day91 import release_gate as gate  # noqa: E402

REGRESSION = [
    "experiments/day64/test_chat_tools.py",
    *[f"experiments/day{d}" for d in range(85, 91)],
    "scripts/day84/test_v10_release.py",
]
SUITES = (
    ("regression", 342, REGRESSION),
    ("release", gate.RELEASE_TESTS, ["scripts/day91/test_release.py"]),
)


def execute(command, directory, root, timeout=900):
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    env.pop("PYTEST_ADDOPTS", None)
    flags = (
        {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        }
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with (
        (directory / "stdout.log").open("wb") as stdout,
        (directory / "stderr.log").open("wb") as stderr,
    ):
        process = subprocess.Popen(
            command,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            shell=False,
            **flags,
        )
        try:
            code = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            cleaned = stop_tree(process)
            raise ValueError(
                "command_interrupted_or_timeout"
                if cleaned
                else "child_cleanup_unverified"
            ) from None
    if code != 0:
        raise ValueError("acceptance_command_failed")


def verify(output, python, root=ROOT):
    root = Path(root).resolve()
    output = Path(output).resolve()
    python = Path(python).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = dict(
        status="running",
        started_at=datetime.now(UTC).isoformat(),
        suites=[],
        new_model_requests=0,
        real_messages_sent=0,
        remote_tag_or_release_checked=False,
    )
    try:
        result["integrity_before"] = gate.validate(root)
        before = gate.digest(root / gate.MANIFEST)
        if not python.is_file():
            raise ValueError("python_environment_missing")
        seen = set()
        for name, expected, paths in SUITES:
            directory = output / name
            directory.mkdir()
            xml = directory / "tests.xml"
            execute(
                [
                    str(python),
                    "-B",
                    "-m",
                    "pytest",
                    *paths,
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--tb=short",
                    f"--junitxml={xml}",
                    f"--basetemp={directory / 'temp'}",
                ],
                directory,
                root,
            )
            counts = junit_counts(xml)
            require_passed(counts, expected)
            identities = {tuple(v) for v in counts.pop("test_ids")}
            if seen.intersection(identities):
                raise ValueError("duplicate_test_across_suites")
            seen.update(identities)
            result["suites"].append(dict(suite=name, **counts))
            atomic_save(output / "progress.json", result)
            print(json.dumps(result["suites"][-1]), flush=True)
        directory = output / "integration"
        directory.mkdir()
        execute(
            [
                str(python),
                "-B",
                str(root / "experiments/day90/runner.py"),
                "run",
                "--suite",
                "full",
                "--output-dir",
                str(directory / "full"),
            ],
            directory,
            root,
        )
        check = scoring.inspect(
            directory / "full/run", directory / "full/evaluation/report.json"
        )
        report = read_json(directory / "full/evaluation/report.json")
        if check["summary"]["passed"] != 12 or not report["full_dataset_evaluated"]:
            raise ValueError("incomplete_fixture_acceptance")
        execution = report["source"]["execution"]
        usage = report["source"]["usage"]["summary"]
        if (
            usage["provider_requests"] != 0
            or usage["input_tokens"] is not None
            or usage["estimated_model_api_cost"] != "0"
        ):
            raise ValueError("fixture_usage_claim_mismatch")
        if any(
            r["observed"]["external_send"]
            or r["observed"]["model_requests"]
            or r["observed"]["simulated_effects"]
            for r in execution["rows"]
        ):
            raise ValueError("unexpected_external_effect")
        result["integrity_after"] = gate.validate(root)
        if gate.digest(root / gate.MANIFEST) != before:
            raise ValueError("manifest_changed_during_verification")
        result.update(
            status="passed",
            completed_at=datetime.now(UTC).isoformat(),
            total_tests=len(seen),
            manifest_sha256_lf=before,
            release_status=result["integrity_after"]["release_status"],
            scoring_summary=report["summary"],
            usage_summary=usage,
            latency_summary=execution["latency_summary"],
            fixture_cases=12,
            fixture_model_attempts=sum(
                r["observed"]["model_attempts"] for r in execution["rows"]
            ),
            mcp_dispatches=sum(
                r["observed"]["mcp_dispatches"] for r in execution["rows"]
            ),
            runtime_python=str(python),
            raw_fixture_run="integration/full",
            scope="342_existing_tests_plus_release_tests_and_12_fresh_fixture_cases",
        )
        names = [
            "regression/tests.xml",
            "release/tests.xml",
            "integration/full/evaluation/report.json",
        ]
        result["output_sha256_lf"] = {
            name: gate.digest(output / name) for name in names
        }
        atomic_save(output / "verification.json", result)
        return result
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        result.update(status="failed", error=type(exc).__name__ + ":" + str(exc))
        atomic_save(output / "failure.json", result)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-python",
        type=Path,
        default=ROOT / "experiments/day73/.venv/Scripts/python.exe",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.output_dir, args.runtime_python)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print(json.dumps(dict(status="failed", output_dir=str(args.output_dir))))
        return 1
    print(
        json.dumps(
            dict(
                status=result["status"],
                total_tests=result["total_tests"],
                score=result["scoring_summary"],
                output_dir=str(args.output_dir),
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
