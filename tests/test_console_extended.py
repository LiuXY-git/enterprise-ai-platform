"""Fixed template/assessment contracts and failure semantics; no external calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.console.application import create_console_app
from backend.app.console.config import ConsoleConfig
from backend.app.console.store import LeaseLost, QueueStore
from backend.app.console.worker import Worker
from backend.app.console.workflow_task import run
from backend.app.console.workflows import TEMPLATES, configured_url
from backend.app.core import lifecycle


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("init_database", "configure_logging", "load_environment"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    with TestClient(create_console_app(ConsoleConfig(tmp_path))) as client:
        yield client


def submit(client, kind="workflow", key="same", **changes):
    body = (
        {
            "template_id": "customer-service",
            "input": TEMPLATES["customer-service"]["example"],
        }
        if kind == "workflow"
        else {}
    )
    body.update(changes)
    return client.post(
        "/workflow-executions" if kind == "workflow" else "/evaluation-runs",
        json=body,
        headers={"Idempotency-Key": key},
    )


@pytest.mark.parametrize("kind", ["workflow", "evaluation"])
def test_idempotency_filter_and_persistence(client, kind):
    with ThreadPoolExecutor(4) as pool:
        responses = list(pool.map(lambda _: submit(client, kind), range(4)))
    assert all(r.status_code == 202 for r in responses)
    assert len({r.json()["job"]["job_id"] for r in responses}) == 1
    changed = submit(
        client,
        kind,
        **(
            {
                "template_id": "email-assistant",
                "input": TEMPLATES["email-assistant"]["example"],
            }
            if kind == "workflow"
            else {"suite": "smoke"}
        ),
    )
    assert changed.status_code == 409
    assert client.get("/jobs?kind=" + kind).json()["total"] == 1
    assert client.get("/jobs?kind=agent").json()["total"] == 0
    job = responses[0].json()["job"]
    assert client.get("/jobs/" + job["job_id"] + "/report").status_code == 409
    store = QueueStore(client.app.state.console_config.database)
    store.initialize()
    assert store.get(job["job_id"])["status"] == "queued"


@pytest.mark.parametrize(
    "key,fields", [(key, value["example"]) for key, value in TEMPLATES.items()]
)
def test_templates_fixture_and_request_validation(client, key, fields):
    response = submit(client, template_id=key, input=fields)
    assert response.status_code == 202
    job = response.json()["job"]
    result = run(
        job, "", httpx.MockTransport(lambda _: pytest.fail("fixture contacted network"))
    )
    assert (
        result["business_status"] == "demo_completed"
        and result["network_requests"] == 0
    )
    assert "n8n_execution_id" not in result["source_ids"]
    assert not result["external_send"]
    assert (
        submit(
            client,
            key="bad",
            template_id=key,
            input={**fields, "url": "http://arbitrary"},
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"template_id": "arbitrary"},
        {"url": "http://bad"},
        {"mode": "live"},
        {"mode": "shell"},
        {"input": {"customer_id": "x", "message": ""}},
        {"input": {"customer_id": "x", "message": "a" * 2001}},
        {"input": {"customer_id": 4, "message": "ok"}},
        {"input": {"customer_id": "x", "message": "ok", "priority": "bad"}},
        {
            "template_id": "sales-followup",
            "input": {
                **TEMPLATES["sales-followup"]["example"],
                "report_date": "2026-02-30",
            },
        },
        {
            "template_id": "sales-followup",
            "input": {
                **TEMPLATES["sales-followup"]["example"],
                "purchase_window_days": 1.5,
            },
        },
    ],
)
def test_bad_workflow_inputs_create_no_jobs(client, changes):
    assert submit(client, **changes).status_code == 422
    assert client.get("/jobs").json()["total"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"dataset_id": "../../file"},
        {"agent_id": "other"},
        {"suite": "arbitrary"},
        {"mode": "live"},
        {"command": "pwd"},
        {"timeout": 1},
    ],
)
def test_bad_evaluation_inputs(client, changes):
    assert submit(client, "evaluation", **changes).status_code == 422
    assert client.get("/jobs").json()["total"] == 0


def test_missing_connection_does_not_dispatch(client):
    job = submit(client, mode="live", confirm_live=True).json()["job"]
    assert Worker(client.app.state.console_config).run(once=True) == 0
    assert (
        client.get("/jobs/" + job["job_id"]).json()["error"]["code"]
        == "configuration_missing"
    )
    assert submit(client, mode="live", confirm_live=True).json()["reused"]


@pytest.mark.parametrize("template", list(TEMPLATES))
def test_live_mapping_and_id_semantics(template):
    job = {
        "job_id": uuid4().hex,
        "mode": "live",
        "input": {"template_id": template, "fields": TEMPLATES[template]["example"]},
    }
    captured = []

    def handler(request):
        captured.append(request)
        assert request.url.path == "/webhook/console-" + template
        data = json.loads(request.content)
        assert data.get("request_id", data.get("event_id")) == "web-" + job["job_id"]
        return httpx.Response(
            200,
            json={
                "n8n_execution_id": "123",
                "console_event_id": "web-" + job["job_id"],
                "workflow_run_id": "business-1",
                "run_id": "business-1",
                "ai_status": "succeeded",
                "status": "succeeded",
                "answer": "safe",
                "api_key": "secret",
                "notification": {"mode": "preview"},
            },
        )

    result = run(job, "http://n8n:5678", httpx.MockTransport(handler))
    assert len(captured) == 1 and result["business_status"] == "succeeded"
    assert result["source_ids"]["n8n_execution_id"] == "123"
    assert (
        result["source_ids"][
            "dify_run_id" if template == "customer-service" else "platform_run_id"
        ]
        == "business-1"
    )
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "failure", ["timeout", "redirect", "http500", "malformed", "missing_id", "oversize"]
)
def test_uncertain_webhook_is_not_retried(failure):
    job = {
        "job_id": uuid4().hex,
        "mode": "live",
        "input": {
            "template_id": "customer-service",
            "fields": TEMPLATES["customer-service"]["example"],
        },
    }
    attempts = []

    def handler(request):
        attempts.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("SECRET", request=request)
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "http://other"})
        if failure == "http500":
            return httpx.Response(500, text="SECRET")
        if failure == "oversize":
            return httpx.Response(200, text="x" * 262145)
        if failure == "missing_id":
            return httpx.Response(200, json={"status": "succeeded"})
        return httpx.Response(200, text="SECRET")

    result = run(job, "http://n8n:5678", httpx.MockTransport(handler))
    assert len(attempts) == 1 and result["business_status"] == "outcome_unknown"
    assert "SECRET" not in json.dumps(result)


def test_saved_report_matches_job_and_never_executes(client):
    job = submit(client, "evaluation").json()["job"]
    store = client.app.state.console_store
    store.acquire("worker", 15)
    store.claim("worker")
    result = {
        "job_id": job["job_id"],
        "summary": {"selected": 12, "passed": 9, "errors": 2, "failed": 1},
        "external_send": False,
    }
    store.finish(job["job_id"], "worker", result=result)
    first = client.get("/jobs/" + job["job_id"] + "/report")
    second = client.get("/jobs/" + job["job_id"] + "/report")
    assert (
        first.json()
        == second.json()
        == client.get("/jobs/" + job["job_id"]).json()["result"]
    )
    assert "attachment" in first.headers["content-disposition"]
    assert client.get("/jobs/missing/report").status_code == 404
    assert client.get("/jobs").json()["total"] == 1


def test_progress_is_persistent_and_fenced(tmp_path):
    store = QueueStore(tmp_path / "q.sqlite")
    store.initialize()
    job, _ = store.submit(
        {"kind": "evaluation", "mode": "fixture", "input": {"suite": "full"}}, "k"
    )
    store.acquire("owner", 15)
    store.claim("owner")
    store.progress(
        job["job_id"], "owner", "evaluating", {"completed": 2, "selected": 12}
    )
    assert QueueStore(store.path).get(job["job_id"])["progress"]["completed"] == 2
    with pytest.raises(LeaseLost):
        store.progress(job["job_id"], "other", "bad", {})
    store.release("owner")
    assert store.get(job["job_id"])["status"] == "interrupted"
    assert store.get(job["job_id"])["progress"]["completed"] == 2


@pytest.mark.parametrize(
    "url", ["ftp://x", "http://user:pass@x", "http://x/path", "http://x?key=x"]
)
def test_bad_server_url_is_not_configured(url):
    assert configured_url(url) is None
