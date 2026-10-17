"""Exercise four fixture sales cases and one explicitly opted-in simulated send."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

try:
    from .verify_api import call
except ImportError:
    from verify_api import call


def verify(base):
    if urlsplit(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("only_localhost_allowed")
    jobs = {}
    for case, expected, amount in [
        ("monthly", "completed", "3000.00"),
        ("customer", "completed", "1550.00"),
        ("empty", "no_data", "0.00"),
        ("clarification", "needs_clarification", None),
    ]:
        body = {"case": case, "mode": "fixture"}
        key = uuid4().hex
        code, first = call(base, "/agent-runs", body=body, key=key)
        assert code == 202 and first["job"]["status"] == "queued"
        code, again = call(base, "/agent-runs", body=body, key=key)
        assert (
            code == 202
            and again["reused"]
            and again["job"]["job_id"] == first["job"]["job_id"]
        )
        job_id = first["job"]["job_id"]
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            code, job = call(base, "/jobs/" + job_id)
            if job["status"] in {"succeeded", "failed", "interrupted"}:
                break
            time.sleep(0.25)
        assert code == 200 and job["status"] == "succeeded", job
        assert job["result"]["business_status"] == expected
        assert (
            job["result"]["external_send"] is False
            and job["result"]["model_requests"] == 0
        )
        if amount is not None:
            assert job["result"]["report"]["total_yuan"] == amount
            _, approval = call(base, "/approvals/" + job["source_ids"]["approval_id"])
            assert (
                approval["effective_status"] == "pending"
                and approval["simulation_count"] == 0
            )
            assert approval["proposal"]["body"] == job["result"]["answer"]
        else:
            assert (
                "approval_id" not in job["source_ids"]
                and job["result"]["receipt"] is None
            )
        jobs[case] = job
    assert len({j["source_ids"]["task_id"] for j in jobs.values()}) == 4
    aid = jobs["monthly"]["source_ids"]["approval_id"]
    route = "/approvals/" + aid + "/decisions"
    _, approval = call(base, "/approvals/" + aid)
    decision = {
        "decision": "approve",
        "confirm": "APPROVE",
        "revision": approval["revision"],
        "digest": approval["digest"],
    }
    assert (
        call(base, route, body={**decision, "digest": "0" * 64}, key=uuid4().hex)[0]
        == 409
    )
    key = uuid4().hex
    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(
            pool.map(lambda _: call(base, route, body=decision, key=key), range(6))
        )
    assert all(code == 200 and data["simulation_count"] == 1 for code, data in replies)
    assert sum(not data["reused"] for _, data in replies) == 1
    assert (
        call(base, route, body=decision, key=uuid4().hex)[1]["decision_result"]
        == "already_executed"
    )
    _, approved = call(base, "/approvals/" + aid)
    assert len(approved["simulated_messages"]) == 1 and not approved["external_send"]
    aid2 = jobs["customer"]["source_ids"]["approval_id"]
    _, other = call(base, "/approvals/" + aid2)
    body = {
        "decision": "reject",
        "confirm": "REJECT",
        "revision": other["revision"],
        "digest": other["digest"],
    }
    code, rejected = call(
        base, "/approvals/" + aid2 + "/decisions", body=body, key=uuid4().hex
    )
    assert (
        code == 200
        and rejected["effective_status"] == "rejected"
        and rejected["simulation_count"] == 0
    )
    return {
        "status": "passed",
        "mode": "fixture",
        "cases": {
            k: {
                "job_id": v["job_id"],
                "source_ids": v["source_ids"],
                "business_status": v["result"]["business_status"],
            }
            for k, v in jobs.items()
        },
        "simulated_sends": 1,
        "external_send": False,
        "model_requests": 0,
        "idempotency": "passed",
        "concurrent_approval": "passed",
        "rejection": "passed",
        "digest_conflict": "passed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080/api")
    parser.add_argument("--simulate-approval", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output file")
    result = verify(args.base_url.rstrip("/"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
