"""Fixed subprocess adapters, bounded execution and fenced progress."""

import json
import os
import subprocess
import sys
import time

from .process_tree import ProcessTree
from .workflows import configured_url


def read_progress(worker, job, output):
    path = output / "evaluation/run/execution/report.json"
    if not path.exists() or path.stat().st_size > 4_000_000:
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        rows = value["rows"]
        selected = 12 if job["input"]["suite"] == "full" else 4
        if len(rows) != selected:
            return
        completed = sum(
            r["execution_status"] not in {"running", "not_run", "interrupted"}
            for r in rows
        )
        active = next(
            (r["case_id"] for r in rows if r["execution_status"] == "running"), None
        )
        worker.store.progress(
            job["job_id"],
            worker.owner,
            "grading" if completed == selected else "evaluating",
            {
                "selected": selected,
                "completed": completed,
                "active_case": active,
                "graded": False,
            },
        )
    except (ValueError, KeyError, OSError):
        return


def execute(worker, job, root, environment):
    kind = job["kind"]
    live = kind == "workflow" and job["mode"] == "live"
    if live and not configured_url(worker.config.n8n_base_url):
        worker.store.finish(
            job["job_id"], worker.owner, error_code="configuration_missing"
        )
        return
    if os.name != "posix":
        worker.store.finish(job["job_id"], worker.owner, error_code="task_failed")
        return
    output = worker.config.data_dir / "runs" / job["job_id"]
    output.mkdir(parents=True, exist_ok=False)
    (output / "request.json").write_text(
        json.dumps(job, ensure_ascii=False), encoding="utf-8"
    )
    if live:
        environment = {
            **environment,
            "WEB_CONSOLE_N8N_BASE_URL": worker.config.n8n_base_url,
        }
    command = [
        sys.executable,
        "-B",
        "-m",
        "backend.app.console." + kind + "_task",
        "--output-dir",
        str(output),
    ]
    timeout = (
        worker.config.evaluation_timeout_seconds
        if kind == "evaluation"
        else worker.config.workflow_timeout_seconds
    )
    process = None
    tree = None
    stderr = None
    try:
        worker.store.progress(
            job["job_id"],
            worker.owner,
            "evaluating" if kind == "evaluation" else "triggering",
            {
                "selected": 12 if job["input"].get("suite") == "full" else 4,
                "completed": 0,
                "graded": False,
            }
            if kind == "evaluation"
            else {"event_id": "web-" + job["job_id"], "automatic_replay": False},
        )
        stderr = (output / "adapter.stderr.log").open("wb")
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=stderr,
        )
        tree = ProcessTree(process.pid)
        deadline = time.monotonic() + timeout
        while True:
            tree.observe()
            if worker.stop.is_set():
                worker.store.finish(
                    job["job_id"],
                    worker.owner,
                    error_code="worker_interrupted",
                    interrupted=True,
                )
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                worker.store.finish(
                    job["job_id"],
                    worker.owner,
                    error_code="workflow_outcome_unknown" if live else "task_timeout",
                )
                return
            worker.store.heartbeat(worker.owner, worker.config.lease_seconds)
            if kind == "evaluation":
                read_progress(worker, job, output)
            try:
                process.wait(timeout=min(remaining, worker.config.heartbeat_seconds))
                break
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            raise ValueError("adapter_failed")
        path = output / "web-result.json"
        if path.stat().st_size > 4_000_000:
            raise ValueError("oversize_result")
        result = json.loads(path.read_text(encoding="utf-8"))
        if (
            result["job_id"] != job["job_id"]
            or result["mode"] != job["mode"]
            or result["external_send"] is not False
        ):
            raise ValueError("result_mismatch")
        if kind == "evaluation":
            if result["suite"] != job["input"]["suite"]:
                raise ValueError("suite_mismatch")
            worker.store.progress(
                job["job_id"],
                worker.owner,
                "graded",
                {
                    "selected": result["summary"]["selected"],
                    "completed": len(
                        [
                            r
                            for r in result["cases"]
                            if r["execution_status"]
                            not in {"not_run", "running", "interrupted"}
                        ]
                    ),
                    "graded": True,
                },
            )
        unknown = kind == "workflow" and result["business_status"] == "outcome_unknown"
        worker.store.finish(
            job["job_id"],
            worker.owner,
            result=result,
            error_code="workflow_outcome_unknown" if unknown else None,
        )
    except (OSError, ValueError, KeyError, TypeError):
        worker.store.finish(
            job["job_id"],
            worker.owner,
            error_code="workflow_outcome_unknown" if live else "invalid_task_result",
        )
    finally:
        if process is not None:
            (tree or ProcessTree(process.pid)).stop(process)
        if stderr is not None:
            stderr.close()
