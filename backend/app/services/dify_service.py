from dataclasses import dataclass
from typing import Any

import httpx

from .dify_config import get_dify_workflow_config


@dataclass(frozen=True)
class DifyWorkflowResult:
    task_id: str
    workflow_run_id: str
    status: str
    answer: str
    outputs: dict[str, Any]
    elapsed_time: float | None
    total_tokens: int | None
    total_steps: int | None


def _extract_answer(outputs: dict[str, Any]) -> str:
    for key in ("answer", "output", "outputString", "text", "result"):
        value = outputs.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    text_values = [
        value.strip()
        for value in outputs.values()
        if isinstance(value, str) and value.strip()
    ]

    if len(text_values) == 1:
        return text_values[0]

    raise RuntimeError("Dify 工作流未返回可识别的文本回答")


async def run_dify_workflow(
    question: str,
    *,
    user: str,
) -> DifyWorkflowResult:
    config = get_dify_workflow_config()

    payload = {
        "inputs": {
            "user_query": question,
        },
        "response_mode": "blocking",
        "user": user,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=config.timeout_seconds,
        ) as client:
            response = await client.post(
                f"{config.base_url}/workflows/run",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Dify 工作流调用失败（HTTP {exc.response.status_code}）",
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError("无法连接 Dify 工作流服务") from exc

    try:
        response_body = response.json()
    except ValueError as exc:
        raise RuntimeError("Dify 工作流返回了无效 JSON") from exc

    data = response_body.get("data")

    if not isinstance(data, dict):
        raise RuntimeError("Dify 工作流响应缺少 data")

    status = data.get("status")

    if status != "succeeded":
        error = data.get("error")
        detail = error if isinstance(error, str) and error else str(status)
        raise RuntimeError(f"Dify 工作流执行失败：{detail}")

    outputs = data.get("outputs")

    if not isinstance(outputs, dict):
        raise RuntimeError("Dify 工作流响应缺少 outputs")

    task_id = response_body.get("task_id")
    workflow_run_id = response_body.get("workflow_run_id")

    if not isinstance(task_id, str) or not isinstance(workflow_run_id, str):
        raise RuntimeError("Dify 工作流响应缺少运行标识")

    return DifyWorkflowResult(
        task_id=task_id,
        workflow_run_id=workflow_run_id,
        status=status,
        answer=_extract_answer(outputs),
        outputs=outputs,
        elapsed_time=data.get("elapsed_time"),
        total_tokens=data.get("total_tokens"),
        total_steps=data.get("total_steps"),
    )
