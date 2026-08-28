import httpx
import pytest

from backend.app.services import dify_service
from backend.app.services.dify_config import DifyWorkflowConfig


class FakeResponse:
    def __init__(
        self,
        body: dict,
        *,
        status_code: int = 200,
    ) -> None:
        self.body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request(
                "POST",
                "http://dify.example/v1/workflows/run",
            )
            response = httpx.Response(
                self.status_code,
                request=request,
            )
            raise httpx.HTTPStatusError(
                "Dify error",
                request=request,
                response=response,
            )

    def json(self) -> dict:
        return self.body


class FakeAsyncClient:
    def __init__(
        self,
        *,
        response: FakeResponse,
        captured: dict,
        timeout: float,
    ) -> None:
        self.response = response
        self.captured = captured
        self.captured["timeout"] = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        json: dict,
        headers: dict,
    ) -> FakeResponse:
        self.captured["url"] = url
        self.captured["json"] = json
        self.captured["headers"] = headers
        return self.response


@pytest.mark.anyio
async def test_run_dify_workflow_returns_answer_and_metadata(
    monkeypatch,
) -> None:
    captured: dict = {}
    config = DifyWorkflowConfig(
        api_key="test-workflow-key",
        base_url="http://dify.example/v1",
        timeout_seconds=45,
    )
    response = FakeResponse(
        {
            "task_id": "task-123",
            "workflow_run_id": "run-123",
            "data": {
                "status": "succeeded",
                "outputs": {
                    "answer": "系统支持 PDF、DOCX 和 Markdown。",
                },
                "elapsed_time": 1.2,
                "total_tokens": 120,
                "total_steps": 6,
            },
        }
    )

    monkeypatch.setattr(
        dify_service,
        "get_dify_workflow_config",
        lambda: config,
    )
    monkeypatch.setattr(
        dify_service.httpx,
        "AsyncClient",
        lambda *, timeout: FakeAsyncClient(
            response=response,
            captured=captured,
            timeout=timeout,
        ),
    )

    result = await dify_service.run_dify_workflow(
        "系统支持哪些文档格式？",
        user="day34-demo-user",
    )

    assert captured["url"] == "http://dify.example/v1/workflows/run"
    assert captured["timeout"] == 45
    assert captured["headers"]["Authorization"] == "Bearer test-workflow-key"
    assert captured["json"] == {
        "inputs": {
            "user_query": "系统支持哪些文档格式？",
        },
        "response_mode": "blocking",
        "user": "day34-demo-user",
    }
    assert result.answer == "系统支持 PDF、DOCX 和 Markdown。"
    assert result.workflow_run_id == "run-123"
    assert result.total_steps == 6


@pytest.mark.anyio
async def test_run_dify_workflow_hides_remote_error_body(
    monkeypatch,
) -> None:
    config = DifyWorkflowConfig(
        api_key="test-workflow-key",
        base_url="http://dify.example/v1",
        timeout_seconds=45,
    )
    response = FakeResponse(
        {
            "message": "sensitive remote detail",
        },
        status_code=401,
    )

    monkeypatch.setattr(
        dify_service,
        "get_dify_workflow_config",
        lambda: config,
    )
    monkeypatch.setattr(
        dify_service.httpx,
        "AsyncClient",
        lambda *, timeout: FakeAsyncClient(
            response=response,
            captured={},
            timeout=timeout,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=r"Dify 工作流调用失败（HTTP 401）",
    ):
        await dify_service.run_dify_workflow(
            "测试问题",
            user="day34-demo-user",
        )
