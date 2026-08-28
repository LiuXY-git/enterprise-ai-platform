from typing import Any

from pydantic import BaseModel, Field


class DifyWorkflowRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="需要提交给 Dify 企业咨询工作流的问题。",
        examples=["系统支持哪些文档格式？"],
    )
    user: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description=("调用方定义的稳定终端用户标识。相同用户应在后续调用中复用该值。"),
        examples=["day34-demo-user"],
    )


class DifyWorkflowResponse(BaseModel):
    task_id: str = Field(
        description="Dify 返回的本次执行任务 ID。",
    )
    workflow_run_id: str = Field(
        description="Dify 中持久保存的工作流运行 ID。",
    )
    status: str = Field(
        description="Dify 工作流执行状态。",
        examples=["succeeded"],
    )
    answer: str = Field(
        description="从工作流最终输出中提取的文本回答。",
    )
    outputs: dict[str, Any] = Field(
        description="Dify 工作流最终输出节点返回的完整变量。",
    )
    elapsed_time: float | None = Field(
        default=None,
        description="Dify 工作流执行耗时，单位为秒。",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Dify 工作流本次执行消耗的 Token 数。",
    )
    total_steps: int | None = Field(
        default=None,
        description="Dify 工作流本次执行的节点步骤数。",
    )
