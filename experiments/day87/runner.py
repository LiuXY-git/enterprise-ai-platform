"""Sequential, bounded fixture execution with isolated evidence and no scoring."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day85.contracts import AgentSpec, canonical_hash  # noqa: E402
from experiments.day86 import dataset_tool as dataset_api  # noqa: E402
from experiments.day87.execution_contracts import (  # noqa: E402
    ExecutionReport,
    ExecutionRow,
    WorkerResult,
)  # noqa: E402

WORKER = Path(__file__).with_name("worker.py")
RUNTIME_DAYS = (64, 65, 72, 73, 78, 79, 80, 82, 85, 86, 87)


def digest(path, *, lf=False):
    raw = Path(path).read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n") if lf else raw).hexdigest()


def atomic_save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def contained(root, relative):
    path = Path(relative)
    target = root / path
    if (
        path.is_absolute()
        or ".." in path.parts
        or not target.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError("artifact_path_outside_run")
    if any(p.is_symlink() for p in [target, *target.parents] if p != root):
        raise ValueError("artifact_symlink")
    return target


def inventory(directory):
    return {
        p.relative_to(directory).as_posix(): digest(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
        and p.name not in {"result.json", "result.json.tmp"}
        and contained(directory, p.relative_to(directory)) == p
    }


def stop_tree(process):
    """Terminate only our child process tree; never leave cleanup silently unverified."""
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
            ok = result.returncode == 0
            if not ok and process.poll() is None:
                # Restricted Windows sessions can deny taskkill. At least stop
                # our direct child, but do not claim that its tree was cleared.
                process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
            ok = True
        process.wait(timeout=5)
        return ok
    except (OSError, subprocess.SubprocessError):
        try:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
        return False


def run_process(command, directory, timeout):
    flags = (
        {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        }
        if os.name == "nt"
        else {"start_new_session": True}
    )
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    try:
        with (
            (directory / "stdout.log").open("wb") as stdout,
            (directory / "stderr.log").open("wb") as stderr,
        ):
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                **flags,
            )
            try:
                return {
                    "code": process.wait(timeout=timeout),
                    "error": None,
                    "cleanup": None,
                }
            except subprocess.TimeoutExpired:
                cleaned = stop_tree(process)
                return {
                    "code": process.returncode,
                    "error": "case_timeout" if cleaned else "cleanup_failed",
                    "cleanup": cleaned,
                }
            except KeyboardInterrupt:
                cleaned = stop_tree(process)
                return {
                    "code": process.returncode,
                    "error": "user_interrupted" if cleaned else "cleanup_failed",
                    "cleanup": cleaned,
                }
    except OSError:
        return {"code": None, "error": "worker_start_failed", "cleanup": None}


def execute_case(case, directory, timeout):
    directory.mkdir()
    command = [
        sys.executable,
        "-B",
        str(WORKER),
        "--case-id",
        case.case_id,
        "--case",
        case.input.case,
        "--scenario",
        case.input.scenario,
        "--output-dir",
        str(directory.resolve()),
    ]
    outcome = run_process(command, directory, timeout)
    error = outcome["error"]
    status = "error"
    observed = None
    if error == "case_timeout":
        status = "timeout"
    elif error == "user_interrupted":
        status = "interrupted"
    elif error is None:
        if outcome["code"] != 0:
            error = "worker_exit_nonzero"
        else:
            try:
                result = WorkerResult.model_validate(
                    dataset_api.read_json(directory / "worker-result.json")
                )
                if (result.case_id, result.case, result.scenario) != (
                    case.case_id,
                    case.input.case,
                    case.input.scenario,
                ):
                    raise ValueError("worker_identity_mismatch")
                for required in (
                    "generation.json",
                    "events.json",
                    "fictional.sqlite",
                    "tasks.sqlite",
                ):
                    if not (directory / "artifacts" / required).is_file():
                        raise ValueError("missing_worker_artifact")
                status, observed = "completed", result.observations
            except (OSError, ValueError, TypeError, KeyError):
                error = "worker_output_invalid"
    row = ExecutionRow(
        case_id=case.case_id,
        execution_status=status,
        observed=observed,
        error=error,
        worker_exit_code=outcome["code"],
        cleanup_verified=outcome["cleanup"],
        artifacts=inventory(directory),
    )
    atomic_save(directory / "result.json", row.model_dump())
    return row


def summarize(rows):
    counts = Counter(row["execution_status"] for row in rows)
    return dict(
        selected=len(rows),
        completed=counts["completed"],
        errors=counts["error"],
        timeouts=counts["timeout"],
        interrupted=counts["interrupted"],
        not_run=counts["not_run"],
        running=counts["running"],
        business_status_counts=dict(
            Counter(
                row["observed"]["business_status"]
                for row in rows
                if row["observed"] is not None
            )
        ),
        success_rate=None,
    )


def persist(directory, report):
    report["summary"] = summarize(report["rows"])
    valid = ExecutionReport.model_validate(report)
    atomic_save(directory / "report.json", valid.model_dump())


def prepare(dataset, agent, suite):
    plan = dataset_api.make_plan(
        dataset_api.load_dataset(dataset),
        AgentSpec.model_validate(dataset_api.read_json(agent)),
        suite,
    )
    gate = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/day84/v10_gate.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    frozen = json.loads(gate.stdout)
    if frozen["status"] != "passed" or frozen["release_status"] != "released":
        raise ValueError("frozen_release_integrity_failed")
    # Capture transitive Python sources too, not just the four Agent identity files.
    files = {
        p
        for day in RUNTIME_DAYS
        for p in (ROOT / f"experiments/day{day}").glob("*.py")
        if not p.name.startswith("test_")
    }
    files |= {ROOT / name for name in plan.dataset.source_sha256_lf}
    hashes = {p.relative_to(ROOT).as_posix(): digest(p, lf=True) for p in sorted(files)}
    return plan, frozen, hashes


def run(
    output,
    *,
    dataset=dataset_api.DATASET,
    agent=dataset_api.AGENT,
    suite="full",
    timeout=60,
):
    if (
        type(timeout) is not int
        or not 5 <= timeout <= 120
        or suite not in {"smoke", "full"}
    ):
        raise ValueError("invalid_runner_options")
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("run_directory_already_exists")
    plan, frozen, hashes = prepare(dataset, agent, suite)
    report = dict(
        schema_version="day87-execution-v1",
        report_kind="execution_record_not_scored_evaluation",
        run_status="running",
        plan=plan.model_dump(),
        plan_sha256=canonical_hash(plan.model_dump()),
        timeout_seconds=timeout,
        execution_mode="fixture_model_real_local_mcp",
        rows=[
            ExecutionRow(case_id=r.case_id, execution_status="not_run").model_dump()
            for r in plan.rows
        ],
        source_sha256_lf=hashes,
        frozen_integrity=frozen,
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    persist(output, report)
    selected = {c.case_id: c for c in plan.dataset.cases}
    active = None
    try:
        for index, row in enumerate(report["rows"]):
            active = index
            row["execution_status"] = "running"
            persist(output, report)
            result = execute_case(
                selected[row["case_id"]], output / "cases" / row["case_id"], timeout
            )
            report["rows"][index] = result.model_dump()
            persist(output, report)
            print(
                json.dumps(
                    {
                        "case_id": result.case_id,
                        "execution_status": result.execution_status,
                        "business_status": result.observed.business_status
                        if result.observed
                        else None,
                    }
                ),
                flush=True,
            )
            if (
                result.execution_status == "interrupted"
                or result.error == "cleanup_failed"
            ):
                report["run_status"] = "interrupted"
                persist(output, report)
                return report
            active = None
        report["run_status"] = (
            "completed"
            if all(r["execution_status"] == "completed" for r in report["rows"])
            else "completed_with_errors"
        )
    except KeyboardInterrupt:
        if (
            active is not None
            and report["rows"][active]["execution_status"] == "running"
        ):
            interrupted = ExecutionRow(
                case_id=report["rows"][active]["case_id"],
                execution_status="interrupted",
                error="user_interrupted",
            )
            case_dir = output / "cases" / interrupted.case_id
            if case_dir.exists():
                interrupted.artifacts = inventory(case_dir)
                atomic_save(case_dir / "result.json", interrupted.model_dump())
            report["rows"][active] = interrupted.model_dump()
        report["run_status"] = "interrupted"
    persist(output, report)
    return report


def inspect(output):
    """Read-only structural/hash audit; never resumes a run or assigns scores."""
    output = Path(output).resolve()
    report = ExecutionReport.model_validate(
        dataset_api.read_json(output / "report.json")
    )
    for row in report.rows:
        directory = contained(output, Path("cases") / row.case_id)
        if row.execution_status in {"not_run", "running"}:
            continue
        if dataset_api.read_json(directory / "result.json") != row.model_dump():
            raise ValueError("case_record_mismatch")
        if inventory(directory) != row.artifacts:
            raise ValueError("artifact_inventory_or_hash_mismatch")
    return {
        "status": "evidence_consistent",
        "run_status": report.run_status,
        "summary": report.summary.model_dump(),
        "judgement": "not_evaluated",
        "agent_executed": False,
        "notice": "local_files_not_signed;_running_means_incomplete_not_liveness_or_resume",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--dataset", type=Path, default=dataset_api.DATASET)
    execute.add_argument("--agent", type=Path, default=dataset_api.AGENT)
    execute.add_argument("--suite", choices=["smoke", "full"], default="full")
    execute.add_argument("--timeout-seconds", type=int, default=60)
    execute.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("inspect")
    check.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result, code = inspect(args.output_dir), 0
        else:
            report = run(
                args.output_dir,
                dataset=args.dataset,
                agent=args.agent,
                suite=args.suite,
                timeout=args.timeout_seconds,
            )
            result = {
                "run_status": report["run_status"],
                "summary": report["summary"],
                "report": str(args.output_dir / "report.json"),
            }
            code = (
                0
                if report["run_status"] == "completed"
                else 130
                if report["run_status"] == "interrupted"
                else 1
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        subprocess.SubprocessError,
    ):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "runner_input_io_or_preflight_failed",
                    "notice": "Existing evidence retained; inspect before a new run.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
