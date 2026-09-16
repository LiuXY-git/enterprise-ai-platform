import json
import logging
from logging.handlers import RotatingFileHandler

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import database
from backend.app import workflow_logging as logs
from backend.app.routers import dify, workflow
from backend.app.services.dify_service import DifyWorkflowResult


@pytest.fixture
def events(monkeypatch):
    captured = []

    class Capture(logging.Handler):
        def emit(self, record):
            captured.append(json.loads(record.getMessage()))

    logger = logging.getLogger(logs.EVENT_LOGGER)
    monkeypatch.setattr(logger, "handlers", [Capture()])
    monkeypatch.setattr(logger, "propagate", False)
    original_level = logger.level
    # setLevel clears isEnabledFor's cache left by earlier route tests.
    logger.setLevel(logging.INFO)
    try:
        yield captured
    finally:
        logger.setLevel(original_level)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "day51.db")
    database.init_database()
    app = FastAPI()
    app.include_router(workflow.router)
    app.include_router(dify.router)
    with TestClient(app) as client:
        yield client


def start_body():
    return {
        "event_id": "day51-demo-event",
        "workflow_name": "mail-demo",
        "source": "mock-email",
        "requester": "demo-user",
        "report_date": "2026-09-14",
        "n8n_execution_id": "execution-51",
        "input_data": {
            "question": "Explain the document formats",
            "api_key": "private-value",
        },
    }


def test_snapshots_redact_nested_secrets_and_preserve_original():
    data = {
        "nested": [{"Authorization": "Bearer abc123", "password": "hidden"}],
        "text": "line1\nline2 token=abcd sk-1234567890",
        "total_tokens": 0,
    }
    encoded = json.dumps(data)
    result = logs.snapshot(data)
    assert "hidden" not in json.dumps(result)
    assert "abc123" not in json.dumps(result)
    assert "abcd" not in json.dumps(result)
    assert "sk-1234567890" not in json.dumps(result)
    assert result["total_tokens"] == 0
    assert json.dumps(data) == encoded


def test_non_finite_numbers_do_not_drop_the_event(events):
    logs.emit_event({"operation": "demo", "duration_ms": float("nan")})
    assert events[-1]["duration_ms"] == "[NON_FINITE_NUMBER]"


def test_large_payloads_keep_log_envelope_and_json_lines(events):
    logs.emit_event(
        {
            "operation": "demo",
            "input": {str(i): "x" * 10000 for i in range(200)},
            "output": "first\nsecond",
            "run_id": "run-51",
        }
    )
    event = events[-1]
    assert event["run_id"] == "run-51"
    assert event["operation"] == "demo"
    assert len(json.dumps(event)) < 12000
    assert len(json.dumps(event).splitlines()) == 1


def test_start_duplicate_finish_record_actual_input_and_client_usage(client, events):
    body = start_body()
    first = client.post("/workflow-runs/start", json=body)
    run_id = first.json()["run_id"]
    assert first.status_code == 200
    assert first.json()["input_data"]["api_key"] == "private-value"
    body["input_data"] = {"question": "different duplicate input"}
    duplicate = client.post("/workflow-runs/start", json=body)
    assert duplicate.json()["should_process"] is False
    assert events[-1]["outcome"] == "duplicate"
    assert events[-1]["input"]["question"] == "Explain the document formats"
    assert events[-1]["total_tokens"] is None
    response = client.patch(
        f"/workflow-runs/{run_id}/result",
        json={
            "status": "succeeded",
            "output_data": {"answer": "PDF and DOCX"},
            "elapsed_time": 1.2,
            "total_tokens": 120,
        },
    )
    assert response.status_code == 200
    event = events[-1]
    assert event["run_id"] == run_id and event["dify_run_id"] is None
    assert event["output"]["answer"] == "PDF and DOCX"
    assert event["input"]["api_key"] == "[REDACTED]"
    assert event["metrics_source"] == "workflow_client_reported"
    assert event["total_tokens"] == 120
    assert event["elapsed_time_seconds"] == 1.2
    assert event["duration_ms"] >= 0
    assert len({e["log_event_id"] for e in events}) == 3


def test_failure_replay_and_rejected_transition_logs(client, events):
    body = start_body()
    run_id = client.post("/workflow-runs/start", json=body).json()["run_id"]
    failed = client.patch(
        f"/workflow-runs/{run_id}/failure",
        json={
            "error_type": "ai_service_unavailable",
            "error_message": "token=hidden",
            "stage": "ai_analysis",
        },
    )
    assert failed.status_code == 200
    assert events[-1]["status"] == "failed"
    assert events[-1]["error_type"] == "ai_service_unavailable"
    assert "hidden" not in json.dumps(events)
    body["replay"] = True
    assert client.post("/workflow-runs/start", json=body).status_code == 200
    assert events[-1]["outcome"] == "replayed"
    assert events[-1]["retry_count"] == 1
    response = client.post("/workflow-runs/start", json=body)
    assert response.status_code == 409
    assert events[-1]["outcome"] == "error"
    assert events[-1]["http_status"] == 409


@pytest.mark.parametrize("tokens", [None, 0, 123])
def test_dify_usage_and_id_namespace(client, events, monkeypatch, tokens):
    async def fake_run(question, *, user):
        return DifyWorkflowResult(
            task_id="task-demo",
            workflow_run_id="dify-run-demo",
            status="succeeded",
            answer="Supported formats",
            outputs={"answer": "Supported formats"},
            elapsed_time=None,
            total_tokens=tokens,
            total_steps=2,
        )

    monkeypatch.setattr(dify, "run_dify_workflow", fake_run)
    response = client.post(
        "/dify/workflow", json={"question": "Formats?", "user": "demo"}
    )
    assert response.status_code == 200
    event = events[-1]
    assert event["run_id"] is None
    assert event["dify_run_id"] == "dify-run-demo"
    assert event["total_tokens"] == tokens
    assert event["elapsed_time_seconds"] is None
    assert event["metrics_source"] == (
        "not_reported" if tokens is None else "dify_response"
    )
    assert event["input"]["question"] == "Formats?"


def test_dify_error_keeps_response_but_does_not_log_exception_body(
    client, events, monkeypatch
):
    async def fake_run(question, *, user):
        raise RuntimeError("token=private-upstream-value")

    monkeypatch.setattr(dify, "run_dify_workflow", fake_run)
    response = client.post(
        "/dify/workflow", json={"question": "Formats?", "user": "demo"}
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "token=private-upstream-value"
    assert events[-1]["http_status"] == 503
    assert events[-1]["output"] is None
    assert "private-upstream-value" not in json.dumps(events)


def test_logging_failure_does_not_undo_success(client, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("disk failure")

    monkeypatch.setattr(logging.getLogger(logs.EVENT_LOGGER), "info", broken)
    response = client.post("/workflow-runs/start", json=start_body())
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert client.get(f"/workflow-runs/{run_id}").status_code == 200


def test_rotating_jsonl_configuration_is_idempotent(tmp_path, monkeypatch):
    logger = logging.getLogger(logs.EVENT_LOGGER)
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "level", logging.INFO)
    monkeypatch.setattr(logger, "propagate", False)
    logs.configure_workflow_logging(tmp_path)
    handlers = list(logger.handlers)
    try:
        logs.configure_workflow_logging(tmp_path)
        assert logger.handlers == handlers
        handler = next(h for h in handlers if isinstance(h, RotatingFileHandler))
        handler.maxBytes = 300
        for i in range(20):
            logs.emit_event(
                {"operation": "rotation-test", "sequence": i, "output": "safe" * 20}
            )
        paths = list(tmp_path.glob("workflow-events.jsonl*"))
        assert len(paths) == 4
        for path in paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                assert json.loads(line)["operation"] == "rotation-test"
    finally:
        for handler in handlers:
            handler.close()
