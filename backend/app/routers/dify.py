from fastapi import APIRouter, HTTPException, status

from ..models.dify import DifyWorkflowRequest, DifyWorkflowResponse
from ..services.dify_service import run_dify_workflow
from ..workflow_logging import observe_workflow

router = APIRouter(
    prefix="/dify",
    tags=["dify"],
)


@router.post(
    "/workflow",
    response_model=DifyWorkflowResponse,
    summary="调用 Dify 企业咨询工作流",
    description=(
        "由 FastAPI 将用户问题转发到已发布的 Dify 企业咨询工作流，"
        "并以阻塞模式返回最终回答和运行元数据。Dify 应用密钥只在服务端读取。"
    ),
    response_description="Dify 工作流的最终回答、输出变量和运行元数据。",
    responses={
        422: {
            "description": "问题或终端用户标识不符合要求。",
        },
        503: {
            "description": "Dify 配置错误、服务不可用或工作流执行失败。",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "无法连接 Dify 工作流服务",
                    },
                },
            },
        },
    },
)
@observe_workflow("dify.call")
async def call_dify_workflow(
    request: DifyWorkflowRequest,
) -> DifyWorkflowResponse:
    try:
        result = await run_dify_workflow(
            request.question,
            user=request.user,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return DifyWorkflowResponse(
        task_id=result.task_id,
        workflow_run_id=result.workflow_run_id,
        status=result.status,
        answer=result.answer,
        outputs=result.outputs,
        elapsed_time=result.elapsed_time,
        total_tokens=result.total_tokens,
        total_steps=result.total_steps,
    )
