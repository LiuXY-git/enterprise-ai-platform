"""HTTP sales/approval tests use local fixture records, no model or notification."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.console.application import create_console_app
from backend.app.console.approvals import ApprovalError, WebApprovalStore
from backend.app.console.config import ConsoleConfig
from backend.app.core import lifecycle


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("init_database", "configure_logging", "load_environment"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    with TestClient(create_console_app(ConsoleConfig(tmp_path))) as client:
        yield client


def create(client, case="monthly", key=None, **extra):
    return client.post(
        "/agent-runs",
        json={"case": case, **extra},
        headers={"Idempotency-Key": key or uuid4().hex},
    )


def seed(client):
    queue = client.app.state.console_store
    job = create(client).json()["job"]
    queue.acquire("test-worker", 15)
    queue.claim("test-worker")
    task_id, run_id = uuid4().hex, uuid4().hex
    body = "教学虚构数据：3000.00 元。来源：" + run_id + "/T1"
    path = (
        client.app.state.console_config.data_dir
        / "runs"
        / job["job_id"]
        / "approvals.sqlite"
    )
    store = WebApprovalStore(path)
    approval = store.create(
        {
            "action": "simulate_send_sales_brief",
            "recipient": "sales-manager-demo",
            "body": body,
            "note": "API test fixture",
            "case": "monthly",
            "source_task_id": task_id,
            "agent_run_id": run_id,
            "source_status": "completed",
            "answer_source": "verified_report_template",
            "degraded": False,
            "fictional": True,
        }
    )
    queue.finish(
        job["job_id"],
        "test-worker",
        result={
            "answer": body,
            "source_ids": {
                "task_id": task_id,
                "run_id": run_id,
                "approval_id": approval["approval_id"],
            },
        },
    )
    queue.release("test-worker")
    return job, approval, store


def decide(client, approval, key=None, **changes):
    body = {
        "decision": "approve",
        "confirm": "APPROVE",
        "revision": approval["revision"],
        "digest": approval["digest"],
    }
    body.update(changes)
    return client.post(
        "/approvals/" + approval["approval_id"] + "/decisions",
        json=body,
        headers={"Idempotency-Key": key or uuid4().hex},
    )


@pytest.mark.parametrize("case", ["monthly", "customer", "empty", "clarification"])
def test_fixed_sales_submissions_are_durable_and_idempotent(client, case):
    first = create(client, case, "same")
    second = create(client, case, "same")
    assert first.status_code == second.status_code == 202
    assert first.json()["job"]["status"] == "queued"
    assert first.json()["job"]["job_id"] == second.json()["job"]["job_id"]
    assert second.json()["reused"]
    assert (
        create(
            client, "customer" if case != "customer" else "monthly", "same"
        ).status_code
        == 409
    )
    assert client.get("/jobs?kind=agent").json()["total"] == 1
    assert client.get("/jobs?kind=smoke").json()["total"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"case": "../../secret"},
        {"case": "monthly", "mode": "live"},
        {"case": "monthly", "year": 2025},
        {"case": "monthly", "output_dir": "/tmp"},
        {"case": True},
        {},
    ],
)
def test_reject_unregistered_inputs(client, body):
    assert (
        client.post(
            "/agent-runs", json=body, headers={"Idempotency-Key": "bad"}
        ).status_code
        == 422
    )
    assert client.get("/jobs").json()["total"] == 0


def test_preview_does_not_send_and_source_binding_is_preserved(client):
    job, approval, _ = seed(client)
    data = client.get("/approvals/" + approval["approval_id"]).json()
    assert data["job_id"] == job["job_id"] and data["effective_status"] == "pending"
    assert (
        data["simulation_count"] == 0
        and data["simulated_messages"] == []
        and not data["external_send"]
    )
    assert client.get("/approvals/" + uuid4().hex).status_code == 404


def test_concurrent_approval_and_retry_create_one_message(client):
    _, approval, store = seed(client)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: decide(client, approval, key="same"), range(8))
        )
    assert all(r.status_code == 200 for r in results)
    assert sum(not r.json()["reused"] for r in results) == 1
    assert decide(client, approval).json()["decision_result"] == "already_executed"
    assert store.show(approval["approval_id"])["simulation_count"] == 1
    display = client.get("/approvals/" + approval["approval_id"]).json()
    assert len(display["simulated_messages"]) == 1 and not display["external_send"]
    assert (
        decide(
            client, approval, key="same", decision="reject", confirm="REJECT"
        ).status_code
        == 409
    )


def test_distinct_concurrent_keys_still_one_message(client):
    _, approval, _ = seed(client)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: decide(client, approval), range(6)))
    assert sum(r.json()["decision_result"] == "executed" for r in results) == 1
    assert all(r.json()["simulation_count"] == 1 for r in results)


@pytest.mark.parametrize(
    "change,expected",
    [({"digest": "0" * 64}, "digest_mismatch"), ({"revision": 2}, "revision_mismatch")],
)
def test_conflicts_do_not_send(client, change, expected):
    _, approval, store = seed(client)
    result = decide(client, approval, **change)
    assert result.status_code == 409 and result.json()["decision_result"] == expected
    assert store.show(approval["approval_id"])["simulation_count"] == 0


def test_expiry_and_rejection_do_not_send(client):
    _, approval, store = seed(client)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE approvals SET expires_at=0")
    assert (
        client.get("/approvals/" + approval["approval_id"]).json()["effective_status"]
        == "expired"
    )
    assert decide(client, approval).json()["decision_result"] == "expired"
    assert store.show(approval["approval_id"])["simulation_count"] == 0
    _, other, other_store = seed(client)
    result = decide(
        client,
        other,
        "reject-key",
        decision="reject",
        confirm="REJECT",
        reason="needs_revision",
    )
    assert result.status_code == 200 and result.json()["effective_status"] == "rejected"
    assert decide(client, other).status_code == 409
    assert decide(
        client,
        other,
        "reject-key",
        decision="reject",
        confirm="REJECT",
        reason="needs_revision",
    ).json()["reused"]
    assert other_store.show(other["approval_id"])["simulation_count"] == 0


def test_confirmation_and_unknown_fields_rejected(client):
    _, approval, store = seed(client)
    assert decide(client, approval, confirm="REJECT").status_code == 422
    assert decide(client, approval, external_send=True).status_code == 422
    assert store.show(approval["approval_id"])["simulation_count"] == 0


def test_different_tasks_have_separate_proposals_and_outboxes(client):
    first, a, sa = seed(client)
    second, b, sb = seed(client)
    assert first["job_id"] != second["job_id"] and sa.path != sb.path
    assert decide(client, a).status_code == 200
    assert sb.show(b["approval_id"])["simulation_count"] == 0
    # A database mapping corruption must not authorize a mismatched proposal.
    with client.app.state.console_store.connection(write=True) as db:
        db.execute(
            "UPDATE console_jobs SET result_json=replace(result_json,?,?) WHERE job_id=?",
            (b["proposal"]["body"], "changed body", second["job_id"]),
        )
    assert decide(client, b).status_code == 409
    assert sb.show(b["approval_id"])["simulation_count"] == 0


def test_receipt_failure_rolls_back_the_simulated_effect(client):
    _, approval, store = seed(client)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TABLE console_decisions(request_key TEXT PRIMARY KEY,fingerprint TEXT,result TEXT)"
        )
        db.execute(
            "CREATE TRIGGER fail_receipt BEFORE INSERT ON console_decisions BEGIN SELECT RAISE(ABORT,'test'); END"
        )
    body = {
        "decision": "approve",
        "confirm": "APPROVE",
        "digest": approval["digest"],
        "revision": 1,
        "reason": "not_needed",
    }
    with pytest.raises(ApprovalError):
        store.decide_once(approval["approval_id"], body, "key")
    state = store.show(approval["approval_id"])
    assert state["effective_status"] == "pending" and state["simulation_count"] == 0


def test_result_and_idempotency_survive_new_app_instance(client):
    _, approval, _ = seed(client)
    assert decide(client, approval, "durable").status_code == 200
    with TestClient(create_console_app(client.app.state.console_config)) as restarted:
        data = restarted.get("/approvals/" + approval["approval_id"]).json()
        assert data["simulation_count"] == 1 and data["effective_status"] == "executed"
        assert decide(restarted, approval, "durable").json()["reused"]
