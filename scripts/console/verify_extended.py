"""Real HTTP/worker checks for workflow fixtures, evaluator reports and isolation."""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new proof path")
    jobs, progress = [], []
    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        caps = client.get("/console/capabilities").raise_for_status().json()

        def submit(endpoint, body):
            key = uuid4().hex
            response = client.post(
                endpoint, json=body, headers={"Idempotency-Key": key}
            )
            assert response.status_code == 202, response.text
            job = response.json()["job"]
            repeated = (
                client.post(endpoint, json=body, headers={"Idempotency-Key": key})
                .raise_for_status()
                .json()
            )
            assert repeated["reused"] and repeated["job"]["job_id"] == job["job_id"]
            return job

        def wait(job):
            deadline = time.monotonic() + 950
            while time.monotonic() < deadline:
                current = client.get("/jobs/" + job["job_id"]).raise_for_status().json()
                if current["kind"] == "evaluation":
                    snapshot = current["progress"]
                    if not progress or progress[-1] != snapshot:
                        progress.append(snapshot)
                if current["status"] not in {"queued", "running"}:
                    return current
                time.sleep(1)
            raise TimeoutError(job["job_id"])

        for template in caps["workflow_templates"]:
            job = wait(
                submit(
                    "/workflow-executions",
                    {
                        "template_id": template["id"],
                        "input": template["example"],
                        "mode": "fixture",
                    },
                )
            )
            assert job["status"] == "succeeded", job
            assert job["result"]["business_status"] == "demo_completed"
            assert job["result"]["network_requests"] == 0
            jobs.append(job)
        if not any(t["live_configured"] for t in caps["workflow_templates"]):
            template = caps["workflow_templates"][0]
            missing = wait(
                submit(
                    "/workflow-executions",
                    {
                        "template_id": template["id"],
                        "input": template["example"],
                        "mode": "live",
                        "confirm_live": True,
                    },
                )
            )
            assert missing["error"]["code"] == "configuration_missing"
            jobs.append(missing)
        for suite, count in [("smoke", 4), ("full", 12)]:
            job = wait(submit("/evaluation-runs", {"suite": suite, "mode": "fixture"}))
            assert job["status"] == "succeeded", job
            result = job["result"]
            assert result["summary"]["selected"] == result["summary"]["passed"] == count
            assert result["summary"]["denominator"] == count
            assert result["full_dataset_evaluated"] == (suite == "full")
            assert result["usage"]["total_tokens"] is None
            assert result["usage"]["estimated_model_api_cost"] == "0"
            report = client.get("/jobs/" + job["job_id"] + "/report").raise_for_status()
            assert report.json() == result
            assert client.get("/jobs/" + job["job_id"] + "/report").json() == result
            assert len(result["cases"]) == count
            assert all(
                "execution_status" in c and "business_status" in c and "judgement" in c
                for c in result["cases"]
            )
            jobs.append(job)
        assert len({j["job_id"] for j in jobs}) == len(jobs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "status": "passed",
                "scope": "real_http_linux_worker_fixture_models",
                "live_dependencies_verified": False,
                "jobs": jobs,
                "progress_snapshots": progress,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "jobs": len(jobs),
                "evaluation_counts": [4, 12],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
