"""Disrupt only an explicitly named disposable acceptance stack, preserving data."""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from verify_api import call

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.project.startswith("eap-console-acceptance-"):
        parser.error(
            "Use a disposable eap-console-acceptance-* project, never the daily deployment"
        )
    if args.output.exists():
        parser.error("Choose a new proof file")
    storage = os.environ.get("WEB_CONSOLE_STORAGE_ROOT")
    if not storage or not Path(storage).is_absolute():
        parser.error(
            "Set WEB_CONSOLE_STORAGE_ROOT to the absolute disposable storage directory"
        )
    prefix = [
        "docker",
        "compose",
        "-p",
        args.project,
        "-f",
        str(ROOT / "compose.console.yaml"),
    ]

    def compose(*command):
        return subprocess.check_output(
            prefix + list(command), cwd=ROOT, text=True, encoding="utf-8", timeout=240
        ).strip()

    # Check ownership before any destructive container operation.
    ids = compose("ps", "-q").splitlines()
    if len(ids) != 3:
        raise ValueError("Expected exactly three running acceptance containers")
    for cid in ids:
        info = json.loads(
            subprocess.check_output(["docker", "inspect", cid], text=True)
        )[0]
        assert info["Config"]["Labels"]["com.docker.compose.project"] == args.project
        for mount in info["Mounts"]:
            if mount["Destination"] == "/app/console-data":
                source = re.sub(
                    r"^/(?:run/desktop/mnt/host|host_mnt)/([a-zA-Z])/",
                    r"\1:/",
                    mount["Source"],
                )
                assert Path(source).resolve() == (Path(storage) / "queue").resolve()
    base = "http://127.0.0.1:18080/api"
    proof = {
        "status": "failed",
        "scope": "disposable_stack_fixture_fault_injection",
        "jobs": {},
        "external_send": False,
    }

    def wait(route, predicate, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                code, value = call(base, route)
                if code == 200 and predicate(value):
                    return value
            except OSError:
                pass
            time.sleep(0.3)
        raise TimeoutError(route)

    try:
        before = call(base, "/jobs?limit=100")[1]["jobs"]
        approvals = {
            j["source_ids"]["approval_id"]: call(
                base, "/approvals/" + j["source_ids"]["approval_id"]
            )[1]["simulation_count"]
            for j in before
            if j["source_ids"].get("approval_id")
        }
        compose("stop", "worker")
        wait("/console/worker", lambda v: v["status"] == "stopped")
        body = {
            "kind": "smoke",
            "mode": "fixture",
            "input": {"message": "queued-before-recreation"},
        }
        key = uuid4().hex
        code, first = call(base, "/jobs", body=body, key=key)
        assert code == 202 and first["job"]["status"] == "queued"
        job_id = first["job"]["job_id"]
        proof["jobs"]["queued"] = job_id
        compose(
            "up", "-d", "--no-deps", "--force-recreate", "--wait", "api", "frontend"
        )
        wait("/jobs/" + job_id, lambda v: v["status"] == "queued")
        assert call(base, "/jobs", body=body, key=key)[1]["reused"]
        compose("start", "worker")
        done = wait("/jobs/" + job_id, lambda v: v["status"] == "succeeded")
        assert done["result"]["echo"] == body["input"]["message"]
        # Hard-kill the worker during a real fixture evaluation, then reclaim its expired lease.
        code, created = call(
            base, "/evaluation-runs", body={"suite": "full"}, key=uuid4().hex
        )
        assert code == 202
        interrupted = created["job"]["job_id"]
        proof["jobs"]["interrupted"] = interrupted
        wait("/jobs/" + interrupted, lambda v: v["status"] == "running")
        compose("kill", "-s", "SIGKILL", "worker")
        wait("/console/worker", lambda v: v["status"] == "stale", 25)
        compose("up", "-d", "--no-deps", "worker")
        stopped = wait("/jobs/" + interrupted, lambda v: v["status"] == "interrupted")
        assert (
            stopped["result"] is None
            and stopped["error"]["code"] == "worker_lease_expired"
        )
        terminal_stamp = stopped["finished_at"]
        # A new task still runs; interrupted work must not silently replay.
        _, next_job = call(
            base,
            "/jobs",
            body={**body, "input": {"message": "new-task-after-interruption"}},
            key=uuid4().hex,
        )
        wait("/jobs/" + next_job["job"]["job_id"], lambda v: v["status"] == "succeeded")
        retained = call(base, "/jobs/" + interrupted)[1]
        assert (
            retained["status"] == "interrupted"
            and retained["finished_at"] == terminal_stamp
        )
        assert call(base, "/jobs/" + interrupted + "/report")[0] == 409
        for old in before:
            now = call(base, "/jobs/" + old["job_id"])[1]
            assert now["result"] == old["result"] and now["status"] == old["status"]
        for aid, count in approvals.items():
            assert call(base, "/approvals/" + aid)[1]["simulation_count"] == count
        proof.update(
            status="passed",
            checks=[
                "queued_survives_recreate",
                "duplicate_submit_reused",
                "worker_stopped_and_stale",
                "killed_run_interrupted",
                "no_replay",
                "new_job_runs",
                "old_results_preserved",
                "approval_counts_preserved",
                "incomplete_report_unavailable",
            ],
        )
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Bring this disposable worker back even if an assertion fails; never replay a task.
        compose("up", "-d", "--no-deps", "worker")
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == "__main__":
    main()
