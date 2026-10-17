"""Check the local API -> SQLite -> worker round trip through the frontend proxy."""

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


def call(base, route, *, body=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    request = Request(
        base + route,
        headers=headers,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8")
        if body is not None
        else None,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def verify(base):
    address = urlsplit(base)
    if address.scheme != "http" or address.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("only_local_http_allowed")
    code, capabilities = call(base, "/console/capabilities")
    if code != 200 or "smoke" not in capabilities["job_kinds"]:
        raise ValueError("capabilities_unavailable")
    key = "day1-" + uuid4().hex
    body = {
        "kind": "smoke",
        "mode": "fixture",
        "input": {"message": "网页任务 UTF-8 验证"},
    }
    code, created = call(base, "/jobs", body=body, key=key)
    if code != 202 or created["job"]["status"] != "queued":
        raise ValueError("submission_failed")
    job_id = created["job"]["job_id"]
    code, repeated = call(base, "/jobs", body=body, key=key)
    if code != 202 or not repeated["reused"] or repeated["job"]["job_id"] != job_id:
        raise ValueError("idempotency_failed")
    changed = {**body, "input": {"message": "different"}}
    if call(base, "/jobs", body=changed, key=key)[0] != 409:
        raise ValueError("conflict_not_rejected")
    if call(base, "/jobs", body={**body, "mode": "live"}, key=uuid4().hex)[0] != 422:
        raise ValueError("invalid_input_not_rejected")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        code, result = call(base, "/jobs/" + job_id)
        if code != 200:
            raise ValueError("job_missing")
        if result["status"] in {"succeeded", "failed", "interrupted"}:
            break
        time.sleep(0.2)
    if result["status"] != "succeeded" or result["result"] != {
        "echo": body["input"]["message"],
        "external_calls": 0,
    }:
        raise ValueError("job_not_successful")
    if call(base, "/console/worker")[1]["status"] != "healthy":
        raise ValueError("worker_not_healthy")
    return {
        "status": "passed",
        "job_id": job_id,
        "idempotency": "passed",
        "conflict": "rejected",
        "invalid_input": "rejected",
        "job_status": result["status"],
        "utf8": "passed",
        "worker": "healthy",
        "external_calls": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080/api")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; choose a new file")
    result = verify(args.base_url.rstrip("/"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
