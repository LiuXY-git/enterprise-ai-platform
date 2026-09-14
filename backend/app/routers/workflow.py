from dataclasses import asdict
from datetime import date
from typing import Never

from fastapi import APIRouter, HTTPException, status

from ..models.workflow import (
    WorkflowRunCheckpointRequest,
    WorkflowRunFailureRequest,
    WorkflowRunFinishRequest,
    WorkflowRunListResponse,
    WorkflowRunRecoveryResponse,
    WorkflowRunResponse,
    WorkflowRunStartRequest,
    WorkflowRunStartResponse,
)
from ..services.workflow_run_service import (
    WorkflowRunConflictError,
    WorkflowRunNotFoundError,
    fail_workflow_run,
    fail_workflow_run_by_execution,
    finish_workflow_run,
    get_workflow_recovery,
    get_workflow_run,
    list_workflow_runs,
    save_workflow_checkpoint,
    start_workflow_run,
)
from ..workflow_logging import observe_workflow

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
@observe_workflow("workflow.start")
def start_run(
    request: WorkflowRunStartRequest,
) -> WorkflowRunStartResponse:
    """创建运行记录，并返回新执行、重复事件或失败回放决策。"""
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
@observe_workflow("workflow.finish")
def finish_run(
    run_id: str,
    request: WorkflowRunFinishRequest,
) -> WorkflowRunResponse:
    """完成运行中的工作流并保存业务输出、分类和资源用量。"""
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
    "/{run_id}/checkpoint",
    response_model=WorkflowRunResponse,
    summary="保存工作流阶段检查点",
)
@observe_workflow("workflow.checkpoint")
def save_checkpoint(
    run_id: str,
    request: WorkflowRunCheckpointRequest,
) -> WorkflowRunResponse:
    """保存通过结构校验的 AI 分析，供 CRM 阶段安全恢复。"""
    try:
        result = save_workflow_checkpoint(
            run_id=run_id,
            stage=request.stage,
            checkpoint_data=request.checkpoint_data,
        )
    except (
        WorkflowRunConflictError,
        WorkflowRunNotFoundError,
    ) as exc:
        _raise_http_error(exc)

    return WorkflowRunResponse(**result)


@router.patch(
    "/{run_id}/failure",
    response_model=WorkflowRunResponse,
    summary="按运行 ID 保存工作流阶段失败",
)
@observe_workflow("workflow.fail")
def fail_run_by_id(
    run_id: str,
    request: WorkflowRunFailureRequest,
) -> WorkflowRunResponse:
    """供受控错误分支保存阶段和脱敏后的安全错误。"""
    try:
        result = fail_workflow_run(
            run_id=run_id,
            error_type=request.error_type,
            error_message=request.error_message,
            failure_stage=request.stage,
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
@observe_workflow("workflow.fail_by_execution")
def fail_run(
    n8n_execution_id: str,
    request: WorkflowRunFailureRequest,
) -> WorkflowRunResponse:
    """供 n8n Error Trigger 按执行 ID 保存自动运行失败。"""
    try:
        result = fail_workflow_run_by_execution(
            n8n_execution_id=n8n_execution_id,
            error_type=request.error_type,
            error_message=request.error_message,
            failure_stage=request.stage,
        )
    except (
        WorkflowRunConflictError,
        WorkflowRunNotFoundError,
    ) as exc:
        _raise_http_error(exc)

    return WorkflowRunResponse(**result)


@router.get(
    "/{run_id}/recovery",
    response_model=WorkflowRunRecoveryResponse,
    summary="查询工作流安全恢复决策",
)
def get_recovery(run_id: str) -> WorkflowRunRecoveryResponse:
    """返回安全恢复起点以及是否需要人工处理。"""
    try:
        result = get_workflow_recovery(run_id)
    except WorkflowRunNotFoundError as exc:
        _raise_http_error(exc)

    return WorkflowRunRecoveryResponse(**result)


@router.get(
    "",
    response_model=WorkflowRunListResponse,
    summary="按日期查询工作流记录",
)
def list_runs(
    report_date: date,
) -> WorkflowRunListResponse:
    """返回指定报告日期的全部工作流运行记录。"""
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
    """按平台生成的运行 ID 返回单条完整记录。"""
    try:
        result = get_workflow_run(run_id)
    except WorkflowRunNotFoundError as exc:
        _raise_http_error(exc)

    return WorkflowRunResponse(**result)
