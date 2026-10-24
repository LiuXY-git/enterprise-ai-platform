"""One outbound webhook attempt; never retry an uncertain external execution."""

import argparse
import json
import os
import time
from pathlib import Path

import httpx

from .workflows import TEMPLATES, configured_url


def payload(job):
    fields = (
        TEMPLATES[job["input"]["template_id"]]["model"]
        .model_validate(job["input"]["fields"])
        .model_dump()
    )
    event = "web-" + job["job_id"]
    if job["input"]["template_id"] == "customer-service":
        return {**fields, "request_id": event}
    return {**fields, "event_id": event, "replay": False, "source": "web-console"}


def normalize(job, raw):
    template = job["input"]["template_id"]
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("n8n_execution_id"), str)
        or not raw["n8n_execution_id"].isdigit()
    ):
        raise ValueError("missing_execution_identity")
    if raw.get("console_event_id") != "web-" + job["job_id"]:
        raise ValueError("submission_binding_mismatch")
    ids = {
        "event_id": "web-" + job["job_id"],
        "n8n_execution_id": raw["n8n_execution_id"],
    }
    run = (
        raw.get("run_id")
        if template == "sales-followup"
        else raw.get("workflow_run_id")
    )
    if not isinstance(run, str) or not 1 <= len(run) <= 128:
        raise ValueError("missing_business_identity")
    ids["dify_run_id" if template == "customer-service" else "platform_run_id"] = run
    status = (
        raw.get("ai_status") if template == "customer-service" else raw.get("status")
    )
    if status not in {
        "succeeded",
        "completed",
        "needs_human_review",
        "duplicate",
        "failed",
        "invalid_request",
    }:
        raise ValueError("unknown_business_status")
    result = {"business_status": status, "source_ids": ids, "output": {}}
    # Only known business output fields are exposed; arbitrary upstream errors/headers are not.
    for key in (
        "answer",
        "summary",
        "draft_reply",
        "category",
        "priority",
        "review_reason",
    ):
        if isinstance(raw.get(key), str):
            result["output"][key] = raw[key][:6000]
    analysis = raw.get("analysis")
    if isinstance(analysis, dict):
        result["output"]["analysis"] = {
            key: analysis[key]
            for key in ("summary", "next_actions", "missing_information")
            if key in analysis
        }
    if template == "sales-followup":
        notification = raw.get("notification", {})
        if (
            not isinstance(notification, dict)
            or notification.get("mode") not in {None, "preview", "disabled"}
            or notification.get("status") in {"sent", "sending"}
        ):
            raise ValueError("unexpected_notification_mode")
        result["output"]["notification"] = "preview_only"
    return result


def run(job, base, transport=None):
    started = time.monotonic()
    template = job["input"]["template_id"]
    request = payload(job)
    result = {
        "job_id": job["job_id"],
        "template_id": template,
        "mode": job["mode"],
        "external_send": False,
        "source_ids": {"event_id": "web-" + job["job_id"]},
        "business_status": "outcome_unknown",
        "output": {},
        "automatic_replay": False,
    }
    if job["mode"] == "fixture":
        text = (
            request.get("message") or request.get("body") or request.get("requirement")
        )
        result.update(
            business_status="demo_completed",
            output={
                "summary": "固定演示：已接收 " + text,
                "draft_reply"
                if template == "email-assistant"
                else "answer": "演示建议：核对资料与需求后人工跟进。",
            },
            notice="固定响应演示，未连接 n8n、Dify 或 Qwen。",
            network_requests=0,
        )
    else:
        if not configured_url(base):
            raise ValueError("configuration_missing")
        try:
            with httpx.Client(
                timeout=90, follow_redirects=False, trust_env=False, transport=transport
            ) as client:
                with client.stream(
                    "POST",
                    base.rstrip("/") + "/webhook/" + TEMPLATES[template]["path"],
                    json=request,
                ) as response:
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > 262144:
                            raise ValueError("oversize_response")
                    if response.status_code >= 300:
                        raise ValueError("upstream_not_success")
                    result.update(normalize(job, json.loads(data)))
            result["notice"] = "已取得 n8n 回执；业务状态与本地任务状态分开显示。"
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            result["notice"] = (
                "外部结果待核对。请在 n8n 按 event_id/request_id 查询执行记录，不要盲目重跑。"
            )
        result["network_requests"] = 1
    result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    path = parser.parse_args().output_dir
    job = json.loads((path / "request.json").read_text(encoding="utf-8"))
    result = run(job, os.getenv("WEB_CONSOLE_N8N_BASE_URL", ""))
    (path / "web-result.json").write_text(
        json.dumps(result, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
