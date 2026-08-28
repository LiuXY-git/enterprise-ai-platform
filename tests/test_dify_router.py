from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import dify as dify_router
from backend.app.services.dify_service import DifyWorkflowResult

app = FastAPI()
app.include_router(dify_router.router)

client = TestClient(app)


def test_call_dify_workflow_returns_result(
    monkeypatch,
) -> None:
    async def fake_run_dify_workflow(
        question: str,
        *,
        user: str,
    ) -> DifyWorkflowResult:
        assert question == "系统支持哪些文档格式？"
        assert user == "day34-demo-user"
        return DifyWorkflowResult(
            task_id="task-123",
            workflow_run_id="run-123",
            status="succeeded",
            answer="系统支持 PDF、DOCX 和 Markdown。",
            outputs={
                "answer": "系统支持 PDF、DOCX 和 Markdown。",
            },
            elapsed_time=1.2,
            total_tokens=120,
            total_steps=6,
        )

    monkeypatch.setattr(
        dify_router,
        "run_dify_workflow",
        fake_run_dify_workflow,
    )

    response = client.post(
        "/dify/workflow",
        json={
            "question": "系统支持哪些文档格式？",
            "user": "day34-demo-user",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "succeeded"
    assert body["answer"] == "系统支持 PDF、DOCX 和 Markdown。"
    assert body["workflow_run_id"] == "run-123"
    assert body["total_steps"] == 6


def test_call_dify_workflow_returns_503(
    monkeypatch,
) -> None:
    async def fake_run_dify_workflow(
        question: str,
        *,
        user: str,
    ) -> DifyWorkflowResult:
        raise RuntimeError("无法连接 Dify 工作流服务")

    monkeypatch.setattr(
        dify_router,
        "run_dify_workflow",
        fake_run_dify_workflow,
    )

    response = client.post(
        "/dify/workflow",
        json={
            "question": "测试问题",
            "user": "day34-demo-user",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "无法连接 Dify 工作流服务"


def test_call_dify_workflow_validates_request() -> None:
    response = client.post(
        "/dify/workflow",
        json={
            "question": "",
            "user": "invalid user",
        },
    )

    assert response.status_code == 422
