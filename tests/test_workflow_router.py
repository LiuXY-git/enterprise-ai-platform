from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import workflow as workflow_router
from backend.app.services.workflow_run_service import (
    WorkflowRunConflictError,
    WorkflowRunNotFoundError,
    WorkflowRunStartResult,
)

app = FastAPI()
app.include_router(workflow_router.router)

client = TestClient(app)


def make_record(
    **overrides,
) -> dict:
    record = {
        "run_id": "run-001",
        "event_id": "mail-day41-001",
        "workflow_name": ("W6D41 - Persistent AI Email Assistant"),
        "source": "mock-email",
        "requester": "customer-001",
        "report_date": "2026-09-03",
        "status": "running",
        "category": None,
        "priority": None,
        "input_data": {
            "event_id": "mail-day41-001",
        },
        "output_data": None,
        "error_type": None,
        "error_message": None,
        "n8n_execution_id": "execution-001",
        "retry_count": 0,
        "duplicate_count": 0,
        "elapsed_time": None,
        "total_tokens": None,
        "started_at": "2026-09-03T09:00:00+08:00",
        "finished_at": None,
        "created_at": "2026-09-03T01:00:00+00:00",
        "updated_at": "2026-09-03T01:00:00+00:00",
    }
    record.update(overrides)
    return record


def test_start_run_returns_idempotency_decision(
    monkeypatch,
) -> None:
    def fake_start_workflow_run(
        **kwargs,
    ) -> WorkflowRunStartResult:
        assert kwargs["event_id"] == "mail-day41-001"
        assert kwargs["report_date"] == "2026-09-03"
        assert kwargs["replay"] is False

        return WorkflowRunStartResult(
            run_id="run-001",
            status="running",
            should_process=True,
            duplicate=False,
            replayed=False,
            retry_count=0,
            duplicate_count=0,
            input_data=kwargs["input_data"],
        )

    monkeypatch.setattr(
        workflow_router,
        "start_workflow_run",
        fake_start_workflow_run,
    )

    response = client.post(
        "/workflow-runs/start",
        json={
            "event_id": "mail-day41-001",
            "workflow_name": ("W6D41 - Persistent AI Email Assistant"),
            "source": "mock-email",
            "requester": "customer-001",
            "report_date": "2026-09-03",
            "input_data": {
                "event_id": "mail-day41-001",
            },
            "n8n_execution_id": "execution-001",
        },
    )

    assert response.status_code == 200
    assert response.json()["run_id"] == "run-001"
    assert response.json()["should_process"] is True
    assert response.json()["duplicate"] is False


def test_start_run_maps_conflict_to_409(
    monkeypatch,
) -> None:
    def fail_start(
        **kwargs,
    ):
        raise WorkflowRunConflictError("只有失败的工作流记录可以回放")

    monkeypatch.setattr(
        workflow_router,
        "start_workflow_run",
        fail_start,
    )

    response = client.post(
        "/workflow-runs/start",
        json={
            "event_id": "mail-day41-001",
            "workflow_name": "W6D41",
            "source": "mock-email",
            "requester": "customer-001",
            "report_date": "2026-09-03",
            "input_data": {},
            "n8n_execution_id": "execution-002",
            "replay": True,
        },
    )

    assert response.status_code == 409


def test_finish_run_returns_updated_record(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        workflow_router,
        "finish_workflow_run",
        lambda **kwargs: make_record(
            status="succeeded",
            output_data=kwargs["output_data"],
            category=kwargs["category"],
            finished_at="2026-09-03T09:00:02+08:00",
        ),
    )

    response = client.patch(
        "/workflow-runs/run-001/result",
        json={
            "status": "succeeded",
            "output_data": {
                "answer": "处理完成",
            },
            "category": "product",
            "priority": "normal",
            "elapsed_time": 2,
            "total_tokens": 100,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["output_data"] == {
        "answer": "处理完成",
    }


def test_finish_run_maps_conflict_to_409(
    monkeypatch,
) -> None:
    def fail_finish(
        **kwargs,
    ):
        raise WorkflowRunConflictError("只有运行中的工作流可以完成")

    monkeypatch.setattr(
        workflow_router,
        "finish_workflow_run",
        fail_finish,
    )

    response = client.patch(
        "/workflow-runs/run-001/result",
        json={
            "status": "succeeded",
            "output_data": {},
        },
    )

    assert response.status_code == 409


def test_failure_route_saves_error(
    monkeypatch,
) -> None:
    def fake_failure(
        **kwargs,
    ) -> dict:
        assert kwargs["n8n_execution_id"] == ("execution-001")
        assert kwargs["error_type"] == "timeout"

        return make_record(
            status="failed",
            error_type=kwargs["error_type"],
            error_message=kwargs["error_message"],
            finished_at="2026-09-03T09:00:05+08:00",
        )

    monkeypatch.setattr(
        workflow_router,
        "fail_workflow_run_by_execution",
        fake_failure,
    )

    response = client.patch(
        ("/workflow-runs/executions/execution-001/failure"),
        json={
            "error_type": "timeout",
            "error_message": "AI request timed out",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_type"] == "timeout"


def test_get_run_maps_missing_record_to_404(
    monkeypatch,
) -> None:
    def fail_get(
        run_id: str,
    ):
        raise WorkflowRunNotFoundError("找不到指定的工作流记录")

    monkeypatch.setattr(
        workflow_router,
        "get_workflow_run",
        fail_get,
    )

    response = client.get("/workflow-runs/missing-run")

    assert response.status_code == 404


def test_list_runs_returns_selected_date(
    monkeypatch,
) -> None:
    def fake_list_workflow_runs(
        *,
        report_date: str,
    ) -> list[dict]:
        assert report_date == "2026-09-03"
        return [
            make_record(),
        ]

    monkeypatch.setattr(
        workflow_router,
        "list_workflow_runs",
        fake_list_workflow_runs,
    )

    response = client.get(
        "/workflow-runs",
        params={
            "report_date": "2026-09-03",
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["report_date"] == ("2026-09-03")


def test_start_run_validates_request() -> None:
    response = client.post(
        "/workflow-runs/start",
        json={
            "event_id": "invalid event id",
            "workflow_name": "",
            "source": "mock email",
            "requester": "invalid user",
            "report_date": "2026-02-30",
            "input_data": {},
            "n8n_execution_id": "",
        },
    )

    assert response.status_code == 422


def test_checkpoint_route_saves_validated_analysis(monkeypatch) -> None:
    def fake_checkpoint(**kwargs):
        assert kwargs["run_id"] == "run-001"
        assert kwargs["stage"] == "analysis_completed"
        return make_record(
            processing_stage="analysis_completed",
            checkpoint_data=kwargs["checkpoint_data"],
        )

    monkeypatch.setattr(
        workflow_router,
        "save_workflow_checkpoint",
        fake_checkpoint,
    )
    response = client.patch(
        "/workflow-runs/run-001/checkpoint",
        json={
            "stage": "analysis_completed",
            "checkpoint_data": {"summary": "validated"},
        },
    )

    assert response.status_code == 200
    assert response.json()["processing_stage"] == "analysis_completed"
    assert response.json()["checkpoint_data"] == {"summary": "validated"}


def test_failure_by_run_route_records_safe_stage(monkeypatch) -> None:
    def fake_failure(**kwargs):
        assert kwargs["failure_stage"] == "crm_transaction"
        return make_record(
            status="failed",
            failure_stage=kwargs["failure_stage"],
            error_type=kwargs["error_type"],
            error_message=kwargs["error_message"],
            finished_at="2026-09-03T09:00:05+08:00",
        )

    monkeypatch.setattr(workflow_router, "fail_workflow_run", fake_failure)
    response = client.patch(
        "/workflow-runs/run-001/failure",
        json={
            "error_type": "crm_transaction_failed",
            "error_message": "CRM transaction failed",
            "stage": "crm_transaction",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["failure_stage"] == "crm_transaction"


def test_recovery_route_returns_human_delivery_check(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_router,
        "get_workflow_recovery",
        lambda run_id: {
            "run_id": run_id,
            "status": "failed",
            "processing_stage": "notification_requested",
            "resume_from": "human_delivery_check",
            "automatic_retry_allowed": False,
            "requires_human_action": True,
            "reason": "通知结果不确定，必须先人工核对实际送达情况",
            "retry_count": 1,
            "checkpoint_data": {"summary": "validated"},
        },
    )
    response = client.get("/workflow-runs/run-001/recovery")

    assert response.status_code == 200
    assert response.json()["resume_from"] == "human_delivery_check"
    assert response.json()["requires_human_action"] is True
