"""Run scoped API/Agent regressions in their existing isolated Python environments."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evidence_layout import workspace  # noqa: E402

# Explicit inventories: all means these suites, not every historical experiment.
SUITES = {
    "api": ("api", ["tests"]),
    "planner": (
        "planner",
        [
            "experiments/day58/test_langgraph_basics.py",
            "experiments/day59/test_task_planner.py",
            "experiments/day60/test_task_progress.py",
        ],
    ),
    "agent": (
        "runtime",
        [
            "experiments/day64/test_chat_tools.py",
            "experiments/day64/test_function_calling.py",
            "experiments/day65/test_sales_sql.py",
            "experiments/day72/test_sales_mcp.py",
            "experiments/day73/test_mcp_agent.py",
            "experiments/day75/test_conversation.py",
        ],
    ),
    "workflow": (
        "runtime",
        [
            "experiments/day78/test_task_log.py",
            "experiments/day79/test_recovery.py",
            "experiments/day80/test_hitl.py",
            "experiments/day81/test_sales_acceptance.py",
            "experiments/day82/test_prompt_lab.py",
        ],
    ),
    "evaluation": (
        "runtime",
        [
            "experiments/day85/test_framework.py",
            "experiments/day86/test_dataset.py",
            "experiments/day87/test_runner.py",
            "experiments/day88/test_latency.py",
            "experiments/day89/test_usage.py",
            "experiments/day90/test_scoring.py",
        ],
    ),
}
COUNTS = ("tests", "failures", "errors", "skipped")
SYSTEM_ENV = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "SYSTEMDRIVE",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "ALLUSERSPROFILE",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "PROCESSOR_ARCHITECTURE",
}


def clean_environment():
    """Forward OS essentials, never caller credentials, tracing or pytest selectors."""
    env = {k: v for k, v in os.environ.items() if k.upper() in SYSTEM_ENV}
    env.update(
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
        HF_HUB_OFFLINE="1",
        ANONYMIZED_TELEMETRY="False",
        NO_COLOR="1",
    )
    return env


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def stop_tree(process):
    """Stop only our owned test child and its tree on timeout/interruption."""
    try:
        if os.name == "nt":
            stopped = (
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                ).returncode
                == 0
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
            stopped = True
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        return stopped
    except (OSError, subprocess.SubprocessError):
        try:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
        return False


def execute(command, root, folder, timeout):
    flags = (
        {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        }
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with (
        (folder / "stdout.log").open("wb") as stdout,
        (folder / "stderr.log").open("wb") as stderr,
    ):
        process = subprocess.Popen(
            command,
            cwd=root,
            env=clean_environment(),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            shell=False,
            **flags,
        )
        try:
            return {"exit_code": process.wait(timeout=timeout)}
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            cleaned = stop_tree(process)
            return {
                "exit_code": process.poll(),
                "cleanup_verified": cleaned,
                "problem": "timeout"
                if isinstance(exc, subprocess.TimeoutExpired)
                else "interrupted",
            }


def read_junit(path):
    tree = ET.parse(path).getroot()
    if tree.tag not in {"testsuites", "testsuite"}:
        raise ValueError("invalid_junit_structure")
    suites = [tree] if tree.tag == "testsuite" else list(tree)
    if not suites or any(
        s.tag != "testsuite" or s.findall("testsuite") for s in suites
    ):
        raise ValueError("invalid_junit_structure")
    counts = dict.fromkeys(COUNTS, 0)
    identities, unsuccessful = set(), []
    for suite in suites:
        declared = {k: int(suite.attrib[k]) for k in COUNTS}
        cases = suite.findall("testcase")
        observed = {
            "tests": len(cases),
            **{
                key: sum(case.find(tag) is not None for case in cases)
                for key, tag in (
                    ("failures", "failure"),
                    ("errors", "error"),
                    ("skipped", "skipped"),
                )
            },
        }
        if declared != observed:
            raise ValueError("inconsistent_junit_counts")
        for case in cases:
            identity = (case.get("classname"), case.get("name"))
            if not all(identity) or identity in identities:
                raise ValueError("missing_or_duplicate_test_identity")
            identities.add(identity)
            for tag in ("failure", "error", "skipped"):
                if case.find(tag) is not None:
                    unsuccessful.append({"id": "::".join(identity), "outcome": tag})
        for key in COUNTS:
            counts[key] += observed[key]
    return {**counts, "unsuccessful": unsuccessful}


def assess(folder, execution):
    """Retain useful counts even on pytest failure; reject incomplete evidence."""
    report = {
        **execution,
        "status": "failed",
        "counts": None,
        "problems": [],
        "test_ids": [],
    }
    if execution.get("problem"):
        report["problems"].append(execution["problem"])
    if execution.get("cleanup_verified") is False:
        report["problems"].append("child_cleanup_unverified")
    if execution.get("exit_code") != 0:
        report["problems"].append("pytest_exit_nonzero")
    try:
        counts = read_junit(folder / "tests.xml")
        report["unsuccessful"] = counts.pop("unsuccessful")
        report["counts"] = counts
        if counts["tests"] <= 0 or any(counts[k] for k in COUNTS[1:]):
            report["problems"].append("tests_not_all_passed")
    except (OSError, ValueError, KeyError, ET.ParseError):
        report["problems"].append("missing_or_invalid_junit")
    try:
        inventory = json.loads((folder / "inventory.json").read_text(encoding="utf-8"))
        collected, executed = inventory["collected"], inventory["executed"]
        if (
            not isinstance(collected, list)
            or not collected
            or not all(isinstance(v, str) and v for v in collected)
            or len(collected) != len(set(collected))
            or not isinstance(executed, list)
            or not all(isinstance(v, str) for v in executed)
            or sorted(collected) != sorted(executed)
            or inventory["exit_code"] != execution.get("exit_code")
            or report["counts"] is None
            or len(collected) != report["counts"]["tests"]
        ):
            raise ValueError("incomplete_inventory")
        report.update(
            test_ids=collected,
            python_version=inventory["python_version"],
            pytest_version=inventory["pytest_version"],
        )
    except (OSError, ValueError, KeyError, TypeError):
        report["problems"].append("missing_or_incomplete_inventory")
    if not report["problems"]:
        report["status"] = "passed"
    return report


def selected_suites(requested):
    if not requested or requested == ["all"]:
        return list(SUITES)
    if "all" in requested or len(requested) != len(set(requested)):
        raise ValueError("duplicate_or_mixed_suite_selection")
    if any(name not in SUITES for name in requested):
        raise ValueError("unknown_suite")
    return [name for name in SUITES if name in requested]


def source_hashes(root):
    """Identify tested code/fixtures; no credentials, runtime databases or reports."""
    hashes = {}
    for directory in (
        "backend",
        "scripts",
        "tests",
        "experiments",
        "evaluation-center",
        "agent-center",
        "n8n",
    ):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and path.suffix in {
                ".py",
                ".json",
                ".txt",
                ".ps1",
                ".cjs",
            }:
                hashes[path.relative_to(root).as_posix()] = hashlib.sha256(
                    path.read_bytes().replace(b"\r\n", b"\n")
                ).hexdigest()
    for name in (
        "conftest.py",
        "pyproject.toml",
        "compose.yaml",
        "requirements.txt",
        "requirements-dev.txt",
    ):
        path = root / name
        if path.is_file():
            hashes[name] = hashlib.sha256(
                path.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
    return hashes


def run(root, output, names, interpreters, timeout=900):
    root, output = Path(root).resolve(), Path(output).resolve()
    if timeout <= 0:
        raise ValueError("timeout_must_be_positive")
    names = selected_suites(names)
    if output.is_relative_to(root) and not output.is_relative_to(
        root / "logs/test-runs"
    ):
        raise ValueError("repository_output_must_be_under_logs_test_runs")
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": 1,
        "status": "running",
        "scope": "selected_offline_regressions",
        "started_at": datetime.now(UTC).isoformat(),
        "selected_suites": names,
        "output_dir": str(output),
        "suites": [{"suite": n, "status": "not_run"} for n in names],
        "limits": [
            "not_live_model_quality",
            "not_browser_or_docker_acceptance",
            "not_all_historical_experiments",
        ],
    }
    save(output / "summary.json", result)
    all_ids = set()
    try:
        for index, name in enumerate(names):
            environment, paths = SUITES[name]
            folder = output / name
            folder.mkdir()
            item = {
                "suite": name,
                "environment": environment,
                "paths": paths,
                "status": "running",
                "counts": None,
            }
            result["suites"][index] = item
            started = time.monotonic()
            try:
                python = Path(interpreters[environment]).resolve()
                item["python"] = str(python)
                if not python.is_file():
                    raise ValueError("python_environment_missing")
                with workspace(root) as copied:
                    manifest = source_hashes(copied)
                    save(folder / "source-manifest.json", manifest)
                    item["source_manifest_sha256"] = hashlib.sha256(
                        (folder / "source-manifest.json").read_bytes()
                    ).hexdigest()
                    if any(not (copied / p).exists() for p in paths):
                        raise ValueError("test_path_missing")
                    command = [
                        str(python),
                        "-B",
                        "-m",
                        "pytest",
                        *paths,
                        "-q",
                        "--tb=short",
                        "-p",
                        "no:cacheprovider",
                    ]
                    if environment == "api":
                        command += ["-p", "anyio.pytest_plugin"]
                    command += [
                        "-p",
                        "scripts.testing.inventory",
                        f"--eap-inventory={folder / 'inventory.json'}",
                        f"--junitxml={folder / 'tests.xml'}",
                        f"--basetemp={folder / 'temp'}",
                    ]
                    item["command"] = command
                    print(json.dumps({"suite": name, "status": "running"}), flush=True)
                    execution = execute(command, copied, folder, timeout)
                    item.update(assess(folder, execution))
                identities = set(item.pop("test_ids"))
                if all_ids.intersection(identities):
                    item["status"] = "failed"
                    item["problems"].append("overlapping_test_suites")
                all_ids.update(identities)
            except (OSError, ValueError, KeyError) as exc:
                item.update(
                    status="failed",
                    problems=[
                        str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                    ],
                )
            finally:
                item["duration_seconds"] = round(time.monotonic() - started, 3)
                save(output / "summary.json", result)
            print(
                json.dumps(
                    {k: item.get(k) for k in ("suite", "status", "counts", "problems")}
                ),
                flush=True,
            )
            if "interrupted" in item.get(
                "problems", []
            ) or "child_cleanup_unverified" in item.get("problems", []):
                break
    except KeyboardInterrupt:
        result["problem"] = "interrupted"
    except (OSError, ValueError) as exc:
        result["problem"] = type(exc).__name__
    result["status"] = (
        "passed"
        if all(s["status"] == "passed" for s in result["suites"])
        and not result.get("problem")
        else "failed"
    )
    result["observed_counts"] = {
        k: sum((s.get("counts") or {}).get(k, 0) for s in result["suites"])
        for k in COUNTS
    }
    result["unique_executed_tests"] = len(all_ids)
    result["completed_at"] = datetime.now(UTC).isoformat()
    save(output / "summary.json", result)
    return result


def default_interpreters(root):
    suffix = "Scripts/python.exe" if os.name == "nt" else "bin/python"
    return {
        "api": root / ".venv" / suffix,
        "planner": root / "experiments/day60/.venv" / suffix,
        "runtime": root / "experiments/day73/.venv" / suffix,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "run"))
    parser.add_argument("--suite", action="append", choices=["all", *SUITES])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Per-suite timeout in seconds (default: 900)",
    )
    defaults = default_interpreters(ROOT)
    for name, path in defaults.items():
        parser.add_argument(f"--{name}-python", type=Path, default=path)
    args = parser.parse_args(argv)
    try:
        names = selected_suites(args.suite)
        interpreters = {n: getattr(args, n + "_python") for n in defaults}
        if args.action == "list":
            print(
                json.dumps(
                    [
                        {
                            "suite": n,
                            "environment": SUITES[n][0],
                            "python": str(interpreters[SUITES[n][0]]),
                            "available": interpreters[SUITES[n][0]].is_file(),
                            "paths": SUITES[n][1],
                        }
                        for n in names
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        output = args.output_dir or ROOT / "logs/test-runs" / (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
        )
        result = run(ROOT, output, names, interpreters, args.timeout)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "status",
                        "observed_counts",
                        "unique_executed_tests",
                        "output_dir",
                    )
                },
                ensure_ascii=False,
            )
        )
        return 0 if result["status"] == "passed" else 1
    except (OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "problem": str(exc)
                    if isinstance(exc, ValueError)
                    else type(exc).__name__,
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
