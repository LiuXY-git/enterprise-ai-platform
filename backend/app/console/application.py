"""Opt-in ASGI entry: legacy API plus local sales tasks and simulated approvals."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Query, Request, Response

from ..application import create_app
from .approvals import ApprovalError, DecisionConflict, for_job
from .config import ConsoleConfig
from .contracts import (
    DecisionRequest,
    JobList,
    JobRequest,
    JobStatus,
    JobView,
    SalesRequest,
    Submission,
    WorkerView,
)
from .extended_routes import install
from .store import JobNotFound, QueueConflict, QueueFull, QueueStore
from .workflows import catalog


def get_store(request: Request) -> QueueStore:
    return request.app.state.console_store


Store = Annotated[QueueStore, Depends(get_store)]
IdempotencyKey = Annotated[
    str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
]

SALES_CASES = [
    {
        "id": "monthly",
        "label": "月度汇总",
        "scope": "2026 年 9 月 · 所有客户 · 最多展示 2 条明细",
    },
    {
        "id": "customer",
        "label": "客户汇总",
        "scope": "2026 年 9 月 · C001 · 最多展示 2 条明细",
    },
    {
        "id": "empty",
        "label": "无数据",
        "scope": "2026 年 7 月 · 所有客户 · 无已支付订单",
    },
    {
        "id": "clarification",
        "label": "缺少条件",
        "scope": "未指定年月 · 提示补充条件，不查询金额",
    },
]


def create_console_app(config: ConsoleConfig | None = None):
    instance = create_app()
    legacy_lifespan = instance.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application) -> AsyncIterator[None]:
        settings = config or ConsoleConfig.from_environment()
        async with legacy_lifespan(application):
            store = QueueStore(settings.database, queue_limit=settings.queue_limit)
            store.initialize()
            application.state.console_store = store
            application.state.console_config = settings
            try:
                yield
            finally:
                del application.state.console_store
                del application.state.console_config

    instance.router.lifespan_context = lifespan

    @instance.get("/console/capabilities", tags=["system"], summary="查询网页任务能力")
    def capabilities(request: Request):
        """Advertise only implemented fixture jobs and local approval operations."""
        settings = request.app.state.console_config
        return {
            "schema_version": 1,
            "implementation_day": 5,
            "modes": ["fixture"],
            "job_kinds": ["smoke", "agent", "workflow", "evaluation"],
            "workflow_modes": ["fixture", "live"],
            "workflow_templates": catalog(settings.n8n_base_url),
            "evaluation_suites": [
                {"id": "full", "count": 12},
                {"id": "smoke", "count": 4},
            ],
            "sales_cases": SALES_CASES,
            "agent_timeout_seconds": settings.agent_timeout_seconds,
            "queue_limit": settings.queue_limit,
            "timeout_seconds": settings.timeout_seconds,
            "agent_runs_available": True,
            "approvals_available": True,
            "workflow_execution_available": True,
            "evaluation_runs_available": True,
            "external_send": False,
        }

    @instance.post(
        "/jobs",
        response_model=Submission,
        status_code=202,
        tags=["system"],
        summary="提交本地验证任务",
    )
    def submit(
        body: JobRequest,
        response: Response,
        store: Store,
        idempotency_key: Annotated[
            str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
        ],
    ):
        """Return a durable task ID without executing the task in the request."""
        try:
            job, reused = store.submit(body.model_dump(), idempotency_key)
        except QueueConflict as exc:
            raise HTTPException(409, "idempotency_key_conflict") from exc
        except QueueFull as exc:
            raise HTTPException(
                429, "queue_full", headers={"Retry-After": "2"}
            ) from exc
        response.headers["Location"] = f"/jobs/{job['job_id']}"
        return {"job": job, "reused": reused}

    @instance.get(
        "/jobs", response_model=JobList, tags=["system"], summary="查询本地任务列表"
    )
    def list_jobs(
        store: Store,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        status: JobStatus | None = None,
        kind: Literal["smoke", "agent", "workflow", "evaluation"] | None = None,
    ):
        """Read saved states; listing never executes, retries or recovers jobs."""
        return store.list(limit=limit, offset=offset, status=status, kind=kind)

    @instance.get(
        "/jobs/{job_id}",
        response_model=JobView,
        tags=["system"],
        summary="查询单条本地任务",
    )
    def get_job(job_id: str, store: Store):
        """Return the persisted result and safe error fields for a task."""
        try:
            return store.get(job_id)
        except JobNotFound as exc:
            raise HTTPException(404, "job_not_found") from exc

    @instance.get(
        "/console/worker",
        response_model=WorkerView,
        tags=["system"],
        summary="查询任务执行器心跳",
    )
    def worker_status(store: Store):
        """Report worker lease health independently from the API health endpoint."""
        return store.worker_status()

    @instance.post(
        "/agent-runs", response_model=Submission, status_code=202, tags=["system"]
    )
    def create_sales(
        body: SalesRequest,
        response: Response,
        store: Store,
        idempotency_key: IdempotencyKey,
    ):
        try:
            job, reused = store.submit(
                {"kind": "agent", "mode": body.mode, "input": {"case": body.case}},
                idempotency_key,
            )
        except QueueConflict as exc:
            raise HTTPException(409, "idempotency_key_conflict") from exc
        except QueueFull as exc:
            raise HTTPException(
                429, "queue_full", headers={"Retry-After": "2"}
            ) from exc
        response.headers["Location"] = f"/jobs/{job['job_id']}"
        return {"job": job, "reused": reused}

    def approval_context(approval_id, request, store):
        try:
            job = store.approval_job(approval_id)
        except JobNotFound as exc:
            raise HTTPException(404, "approval_not_found") from exc
        approval = for_job(request.app.state.console_config, job)
        approval.display(approval_id, job)  # Check source binding before any write.
        return approval, job

    @instance.get("/approvals/{approval_id}", tags=["system"])
    def get_approval(approval_id: str, request: Request, store: Store):
        try:
            approval, job = approval_context(approval_id, request, store)
            return approval.display(approval_id, job)
        except ApprovalError as exc:
            raise HTTPException(409, "approval_unavailable_or_inconsistent") from exc

    @instance.post("/approvals/{approval_id}/decisions", tags=["system"])
    def decide(
        approval_id: str,
        body: DecisionRequest,
        request: Request,
        response: Response,
        store: Store,
        idempotency_key: IdempotencyKey,
    ):
        try:
            approval, job = approval_context(approval_id, request, store)
            decision = approval.decide_once(
                approval_id, body.model_dump(), idempotency_key
            )
            current = approval.display(approval_id, job)
            if decision["decision_result"] not in {
                "executed",
                "already_executed",
                "rejected",
            }:
                response.status_code = 409
            return {
                **current,
                "decision_result": decision["decision_result"],
                "reused": decision["reused"],
            }
        except DecisionConflict as exc:
            raise HTTPException(409, "idempotency_key_conflict") from exc
        except ApprovalError as exc:
            raise HTTPException(409, "approval_unavailable_or_inconsistent") from exc

    install(instance)
    return instance


app = create_console_app()
