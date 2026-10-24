"""Day-one HTTP contracts and compatibility with the default platform app."""

import pytest
from fastapi.testclient import TestClient

from backend.app.application import create_app
from backend.app.console.application import create_console_app
from backend.app.console.config import ConsoleConfig
from backend.app.console.worker import Worker
from backend.app.core import lifecycle


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("init_database", "configure_logging", "load_environment"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    with TestClient(
        create_console_app(ConsoleConfig(tmp_path, queue_limit=2))
    ) as client:
        yield client


def post(client, key="example", **overrides):
    body = {"kind": "smoke", "mode": "fixture", "input": {"message": "你好"}}
    body.update(overrides)
    return client.post("/jobs", json=body, headers={"Idempotency-Key": key})


def test_api_returns_immediately_then_worker_runs(client):
    response = post(client)
    assert response.status_code == 202
    job = response.json()["job"]
    assert job["status"] == "queued" and job["started_at"] is None
    assert response.headers["location"] == "/jobs/" + job["job_id"]
    assert client.get("/console/worker").json()["status"] == "missing"
    # No task is executed by POST or GET, even with no worker running.
    assert client.get(response.headers["location"]).json()["status"] == "queued"
    assert Worker(client.app.state.console_config).run(once=True) == 0
    result = client.get(response.headers["location"]).json()
    assert result["status"] == "succeeded" and result["result"]["echo"] == "你好"
    again = post(client)
    assert again.json()["reused"]
    assert again.json()["job"]["job_id"] == job["job_id"]
    assert client.get("/jobs").json()["total"] == 1


def test_conflict_full_queue_not_found_and_limits(client):
    assert post(client).status_code == 202
    assert post(client, input={"message": "changed"}).status_code == 409
    assert post(client, key="second").status_code == 202
    full = post(client, key="third")
    assert full.status_code == 429 and full.headers["retry-after"] == "2"
    assert post(client).json()["reused"]
    assert client.get("/jobs/missing").status_code == 404
    for query in ("limit=0", "limit=101", "offset=-1", "status=unknown"):
        assert client.get("/jobs?" + query).status_code == 422
    assert client.get("/jobs?status=queued&limit=1&offset=1").json()["total"] == 2


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "agent"},
        {"mode": "live"},
        {"command": "anything"},
        {"input": {"message": ""}},
        {"input": {"message": "a" * 201}},
        {"input": {"message": 42}},
        {"input": {"message": "ok", "path": "../../secret"}},
    ],
)
def test_invalid_payloads_never_create_jobs(client, change):
    assert post(client, **change).status_code == 422
    assert client.get("/jobs").json()["total"] == 0


def test_idempotency_header_is_required_and_validated(client):
    assert client.post("/jobs", json={"input": {"message": "x"}}).status_code == 422
    assert post(client, key="bad key").status_code == 422
    assert post(client, key="a" * 129).status_code == 422


def test_capabilities_advertise_implemented_modules(client):
    body = client.get("/console/capabilities").json()
    assert body["job_kinds"] == ["smoke", "agent", "workflow", "evaluation"] and body["modes"] == ["fixture"]
    assert body["agent_runs_available"] and body["approvals_available"]
    assert body["workflow_execution_available"] and body["evaluation_runs_available"]
    assert not body["external_send"]
    assert client.post("/agent-runs", json={}).status_code == 422
    assert client.get("/health").json() == {"status": "ok"}


def test_default_application_and_existing_contracts_are_preserved():
    default = create_app().openapi()
    console = create_console_app().openapi()
    assert "/jobs" not in default["paths"]
    assert all(
        console["paths"][key] == value for key, value in default["paths"].items()
    )
    assert all(
        console["components"]["schemas"][key] == value
        for key, value in default["components"]["schemas"].items()
    )


def test_constructing_console_app_does_not_create_data(tmp_path):
    target = tmp_path / "not-created"
    create_console_app(ConsoleConfig(target))
    assert not target.exists()
