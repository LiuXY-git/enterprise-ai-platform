"""Single leased worker with a fixed subprocess command and bounded execution."""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from .config import ConsoleConfig
from .store import LeaseLost, QueueStore, encoded

ROOT = Path(__file__).resolve().parents[3]


def child_environment():
    # Do not propagate model keys or arbitrary Python startup/import settings.
    permitted = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "HOME",
    }
    environment = {k: v for k, v in os.environ.items() if k.upper() in permitted}
    environment.update(
        PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1"
    )
    return environment


class Worker:
    def __init__(self, config, *, stop=None):
        self.config = config
        self.store = QueueStore(config.database, queue_limit=config.queue_limit)
        self.owner = uuid4().hex
        self.stop = stop or threading.Event()

    def execute(self, job):
        if job["kind"] == "agent" and job["mode"] == "fixture":
            from .sales_worker import execute_sales

            return execute_sales(self, job, ROOT, child_environment())
        if job["kind"] != "smoke" or job["mode"] != "fixture":
            self.store.finish(job["job_id"], self.owner, error_code="task_failed")
            return
        command = [sys.executable, "-B", "-m", "backend.app.console.smoke"]
        deadline = time.monotonic() + self.config.timeout_seconds
        process = None
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=child_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
            )
            payload = encoded(job["input"])
            while True:
                if self.stop.is_set():
                    self.store.finish(
                        job["job_id"],
                        self.owner,
                        error_code="worker_interrupted",
                        interrupted=True,
                    )
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.store.finish(
                        job["job_id"], self.owner, error_code="task_timeout"
                    )
                    return
                self.store.heartbeat(self.owner, self.config.lease_seconds)
                try:
                    output, _ = process.communicate(
                        input=payload,
                        timeout=min(self.config.heartbeat_seconds, remaining),
                    )
                    break
                except subprocess.TimeoutExpired:
                    payload = None
            if process.returncode:
                self.store.finish(job["job_id"], self.owner, error_code="task_failed")
                return
            if len(output) > 4096:
                raise ValueError("output_too_large")
            result = json.loads(output)
            if result != {"echo": job["input"]["message"], "external_calls": 0}:
                raise ValueError("unexpected_result")
            self.store.finish(job["job_id"], self.owner, result=result)
        except (ValueError, UnicodeError):
            self.store.finish(
                job["job_id"], self.owner, error_code="invalid_task_result"
            )
        except OSError:
            self.store.finish(job["job_id"], self.owner, error_code="task_failed")
        finally:
            # Day-one child cannot create descendants. Business adapters require
            # process-group cleanup before they are enabled on later days.
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.communicate()

    def run(self, *, once=False):
        self.store.initialize()
        if not self.store.acquire(self.owner, self.config.lease_seconds):
            print('{"status":"worker_already_running"}', flush=True)
            return 2
        try:
            while not self.stop.is_set():
                self.store.heartbeat(self.owner, self.config.lease_seconds)
                job = self.store.claim(self.owner)
                if job:
                    self.execute(job)
                    print(
                        encoded(
                            {
                                "job_id": job["job_id"],
                                "status": self.store.get(job["job_id"])["status"],
                            }
                        ),
                        flush=True,
                    )
                if once:
                    return 0
                self.stop.wait(self.config.poll_seconds)
            return 0
        except LeaseLost:
            print('{"status":"worker_lease_lost"}', flush=True)
            return 3
        finally:
            self.store.release(self.owner)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args(argv)
    config = ConsoleConfig.from_environment()
    if args.healthcheck:
        if not config.database.is_file():
            return 1
        store = QueueStore(config.database)
        return int(store.worker_status()["status"] != "healthy")
    worker = Worker(config)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: worker.stop.set())
    return worker.run(once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
