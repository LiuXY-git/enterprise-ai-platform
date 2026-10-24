"""Queued template executions, fixed evaluations and immutable saved reports."""

import json
from typing import Annotated

from fastapi import Header, HTTPException, Request, Response

from .contracts import EvaluationRequest, Submission
from .store import JobNotFound, QueueConflict, QueueFull
from .workflows import WorkflowRequest

Key = Annotated[
    str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
]


def install(app):
    def submit(request, response, payload, key):
        store = request.app.state.console_store
        try:
            job, reused = store.submit(payload, key)
        except QueueConflict as exc:
            raise HTTPException(409, "idempotency_key_conflict") from exc
        except QueueFull as exc:
            raise HTTPException(
                429, "queue_full", headers={"Retry-After": "2"}
            ) from exc
        response.headers["Location"] = "/jobs/" + job["job_id"]
        return {"job": job, "reused": reused}

    @app.post(
        "/workflow-executions",
        response_model=Submission,
        status_code=202,
        tags=["system"],
    )
    def workflow(
        body: WorkflowRequest,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ):
        return submit(
            request,
            response,
            {
                "kind": "workflow",
                "mode": body.mode,
                "input": {"template_id": body.template_id, "fields": body.input},
            },
            idempotency_key,
        )

    @app.post(
        "/evaluation-runs", response_model=Submission, status_code=202, tags=["system"]
    )
    def evaluation(
        body: EvaluationRequest,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ):
        return submit(
            request,
            response,
            {
                "kind": "evaluation",
                "mode": body.mode,
                "input": body.model_dump(exclude={"mode"}),
            },
            idempotency_key,
        )

    @app.get("/jobs/{job_id}/report", tags=["system"])
    def report(job_id: str, request: Request):
        try:
            job = request.app.state.console_store.get(job_id)
        except JobNotFound as exc:
            raise HTTPException(404, "job_not_found") from exc
        if job["kind"] != "evaluation" or not job["result"]:
            raise HTTPException(409, "report_not_ready")
        return Response(
            json.dumps(job["result"], ensure_ascii=False, allow_nan=False, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="evaluation-{job["job_id"]}.json"',
                "Cache-Control": "no-store",
            },
        )
