from dataclasses import asdict
from datetime import date
from typing import Never

from fastapi import APIRouter, HTTPException, status

from ..models.workflow import (
    WorkflowRunFailureRequest,
    WorkflowRunFinishRequest,
    WorkflowRunListResponse,
    WorkflowRunResponse,
    WorkflowRunStartRequest,
    WorkflowRunStartResponse,
)
from ..services.workflow_run_service import (
    WorkflowRunConflictError,
    WorkflowRunNotFoundError,
    fail_workflow_run_by_execution,
    finish_workflow_run,
    get_workflow_run,
    list_workflow_runs,
    start_workflow_run,
)

router = APIRouter(
    prefix="/workflow-runs",
    tags=["workflows"],
)


def _raise_http_error(
    exc: RuntimeError,
) -> Never:
    if isinstance(
        exc,
        WorkflowRunNotFoundError,
    ):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_409_CONFLICT

    raise HTTPException(
        status_code=status_code,
        detail=str(exc),
    ) from exc


@router.post(
    "/start",
    response_model=WorkflowRunStartResponse,
    summary="登记工作流运行",
)
def start_run(
    request: WorkflowRunStartRequest,
) -> WorkflowRunStartResponse:
    try:
        result = start_workflow_run(
            event_id=request.event_id,
            workflow_name=request.workflow_name,
            source=request.source,
            requester=request.requester,
            report_date=request.report_date.isoformat(),
            input_data=request.input_data,
            n8n_execution_id=request.n8n_execution_id,
            replay=request.replay,
        )
    except WorkflowRunConflictError as exc:
        _raise_http_error(exc)

    return WorkflowRunStartResponse(**asdict(result))


@router.patch(
    "/{run_id}/result",
    response_model=WorkflowRunResponse,
    summary="保存工作流处理结果",
)
def finish_run(
    run_id: str,
    request: WorkflowRunFinishRequest,
) -> WorkflowRunResponse:
    try:
        result = finish_workflow_run(
            run_id=run_id,
            status=request.status,
            output_data=request.output_data,
            category=request.category,
            priority=request.priority,
            elapsed_time=request.elapsed_time,
            total_tokens=request.total_tokens,
        )
    except (
        WorkflowRunConflictError,
        WorkflowRunNotFoundError,
    ) as exc:
        _raise_http_error(exc)

    return WorkflowRunResponse(**result)


@router.patch(
    "/executions/{n8n_execution_id}/failure",
    response_model=WorkflowRunResponse,
    summary="保存 n8n 执行失败",
)
def fail_run(
    n8n_execution_id: str,
    request: WorkflowRunFailureRequest,
) -> WorkflowRunResponse:
    try:
        result = fail_workflow_run_by_execution(
            n8n_execution_id=n8n_execution_id,
            error_type=request.error_type,
            error_message=request.error_message,
        )
    except (
        WorkflowRunConflictError,
        WorkflowRunNotFoundError,
    ) as exc:
        _raise_http_error(exc)

    return WorkflowRunResponse(**result)


@router.get(
    "",
    response_model=WorkflowRunListResponse,
    summary="按日期查询工作流记录",
)
def list_runs(
    report_date: date,
) -> WorkflowRunListResponse:
    records = list_workflow_runs(
        report_date=report_date.isoformat(),
    )

    return WorkflowRunListResponse(
        report_date=report_date,
        count=len(records),
        runs=[WorkflowRunResponse(**record) for record in records],
    )


@router.get(
    "/{run_id}",
    response_model=WorkflowRunResponse,
    summary="查询单条工作流记录",
)
def get_run(
    run_id: str,
) -> WorkflowRunResponse:
    try:
        result = get_workflow_run(run_id)
    except WorkflowRunNotFoundError as exc:
        _raise_http_error(exc)

    return WorkflowRunResponse(**result)
