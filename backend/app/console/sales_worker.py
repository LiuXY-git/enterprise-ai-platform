"""Bounded Linux process group execution for the fixed sales adapter."""

import os
import re
import signal
import subprocess
import sys
import time

from .contracts import SalesResult


def stop_group(process):
    # Kill the whole session even if the leader exited but left an MCP child.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def execute_sales(worker, job, root, environment):
    if os.name != "posix":
        worker.store.finish(job["job_id"], worker.owner, error_code="task_failed")
        return
    if not re.fullmatch(r"[0-9a-f]{32}", job["job_id"]):
        raise ValueError("invalid_job_id")
    output = worker.config.data_dir / "runs" / job["job_id"]
    command = [
        sys.executable,
        "-B",
        "-m",
        "backend.app.console.sales_task",
        "--case",
        job["input"]["case"],
        "--output-dir",
        str(output),
    ]
    process = None
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + worker.config.agent_timeout_seconds
        while True:
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
                    job["job_id"], worker.owner, error_code="task_timeout"
                )
                return
            worker.store.heartbeat(worker.owner, worker.config.lease_seconds)
            try:
                process.wait(timeout=min(remaining, worker.config.heartbeat_seconds))
                break
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            worker.store.finish(job["job_id"], worker.owner, error_code="task_failed")
            return
        path = output / "web-result.json"
        if path.stat().st_size > 262144:
            raise ValueError("oversize_sales_result")
        result = SalesResult.model_validate_json(path.read_bytes())
        if result.case != job["input"]["case"]:
            raise ValueError("result_case_mismatch")
        worker.store.finish(job["job_id"], worker.owner, result=result.model_dump())
    except (ValueError, KeyError, UnicodeError):
        worker.store.finish(
            job["job_id"], worker.owner, error_code="invalid_task_result"
        )
    except OSError:
        worker.store.finish(job["job_id"], worker.owner, error_code="task_failed")
    finally:
        if process is not None:
            stop_group(process)
