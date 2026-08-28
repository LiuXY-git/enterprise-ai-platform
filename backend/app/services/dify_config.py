import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class DifyWorkflowConfig:
    api_key: str
    base_url: str
    timeout_seconds: float


def get_dify_workflow_config() -> DifyWorkflowConfig:
    api_key = os.getenv(
        "DIFY_WORKFLOW_API_KEY",
        "",
    ).strip()
    base_url = os.getenv(
        "DIFY_API_BASE_URL",
        "http://localhost/v1",
    ).strip()
    timeout_value = os.getenv(
        "DIFY_WORKFLOW_TIMEOUT_SECONDS",
        "120",
    ).strip()

    if not api_key:
        raise RuntimeError("未配置 DIFY_WORKFLOW_API_KEY")

    if not base_url:
        raise RuntimeError("未配置 DIFY_API_BASE_URL")

    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise RuntimeError(
            "DIFY_WORKFLOW_TIMEOUT_SECONDS 必须是数字",
        ) from exc

    if timeout_seconds <= 0:
        raise RuntimeError(
            "DIFY_WORKFLOW_TIMEOUT_SECONDS 必须大于 0",
        )

    return DifyWorkflowConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
    )
