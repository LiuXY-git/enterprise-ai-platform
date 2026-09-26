"""Approval binding, atomic local effect, concurrency and separate-process CLI."""

import copy
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hitl_agent as hitl  # noqa: E402
from approval_store import ApprovalError, ApprovalStore, digest  # noqa: E402


@pytest.fixture
def proposal():
    return {
        "action": "simulate_send_sales_brief",
        "recipient": "sales-manager-demo",
        "body": "教学虚构数据：4 单，3000.00 元。来源：" + "b" * 32 + "/T1",
        "note": "",
        "source_task_id": "a" * 32,
        "agent_run_id": "b" * 32,
        "source_status": "completed",
        "answer_source": "verified_report_template",
        "degraded": False,
        "fictional": True,
        "case": "monthly",
    }


@pytest.fixture
def clock():
    return [2_000_000_000]


@pytest.fixture
def store(tmp_path, clock):
    return ApprovalStore(tmp_path / "approvals.sqlite", clock=lambda: clock[0])


def decide(store, card, decision="approve"):
    return store.decide(card["approval_id"], card["digest"], decision)


def test_create_never_executes_and_initial_request_is_idempotent(store, proposal):
    card = store.create(proposal)
    assert card["status"] == "pending" and card["simulation_count"] == 0
    assert card["proposal"] == proposal and not card["external_send"]
    again = store.create(proposal, ttl=1)
    assert card == again
    assert len(store.list()["approvals"]) == 1


def test_approve_atomic_effect_and_duplicate_approval(store, proposal):
    card = store.create(proposal)
    result = decide(store, card)
    assert result["status"] == "executed" and result["simulation_count"] == 1
    assert [e["kind"] for e in result["events"]] == [
        "approval_requested",
        "human_approved",
        "simulation_executed",
    ]
    again = decide(store, card)
    assert (
        again["decision_result"] == "already_executed"
        and again["simulation_count"] == 1
    )
    assert again["events"] == result["events"]
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM simulated_outbox").fetchone()[0] == 1
        assert (
            json.loads(
                db.execute("SELECT proposal FROM simulated_outbox").fetchone()[0]
            )
            == proposal
        )


def test_rejection_cannot_later_execute(store, proposal):
    card = store.create(proposal)
    rejected = decide(store, card, "reject")
    assert rejected["status"] == "rejected" and rejected["simulation_count"] == 0
    assert decide(store, card)["decision_result"] == "not_pending"
    assert store.show(card["approval_id"])["simulation_count"] == 0


@pytest.mark.parametrize("offset", [0, 1, 60])
def test_expiration_boundary_is_not_approval(store, proposal, clock, offset):
    card = store.create(proposal, ttl=10)
    clock[0] += 10 + offset
    before = store.path.read_bytes()
    view = store.show(card["approval_id"])
    assert view["status"] == "pending" and view["effective_status"] == "expired"
    assert store.list()["approvals"][0]["effective_status"] == "expired"
    assert store.path.read_bytes() == before
    result = decide(store, card)
    assert result["decision_result"] == result["status"] == "expired"
    assert result["simulation_count"] == 0


def test_approve_just_before_expiry_and_repeated_after_expiry(store, proposal, clock):
    card = store.create(proposal, ttl=10)
    clock[0] += 9
    assert decide(store, card)["status"] == "executed"
    clock[0] += 100
    assert decide(store, card)["decision_result"] == "already_executed"


@pytest.mark.parametrize(
    "change", [{"recipient": "finance-demo"}, {"note": "请复核后归档"}]
)
def test_revision_invalidates_old_approval(store, proposal, change):
    old = store.create(proposal)
    new = store.revise(old["approval_id"], old["digest"], **change)
    assert new["approval_id"] != old["approval_id"] and new["digest"] != old["digest"]
    assert new["parent_id"] == old["approval_id"] and new["revision"] == 2
    assert new["status"] == "pending" and new["simulation_count"] == 0
    assert decide(store, old)["status"] == "superseded"
    stale = store.decide(new["approval_id"], old["digest"], "approve")
    assert (
        stale["decision_result"] == "digest_mismatch" and stale["simulation_count"] == 0
    )
    assert decide(store, new)["simulation_count"] == 1


def test_wrong_digest_never_authorizes(store, proposal):
    card = store.create(proposal)
    for token in ("", "APPROVE", "0" * 64):
        blocked = store.decide(card["approval_id"], token, "approve")
        assert blocked["decision_result"] == "digest_mismatch"
        assert blocked["status"] == "pending" and blocked["simulation_count"] == 0
    assert decide(store, card)["status"] == "executed"


def test_proposal_tamper_detected(store, proposal):
    card = store.create(proposal)
    changed = copy.deepcopy(proposal)
    changed["body"] += "changed without approval"
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE approvals SET proposal=?", (json.dumps(changed),))
    with pytest.raises(ApprovalError):
        decide(store, card)
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM simulated_outbox").fetchone()[0] == 0


@pytest.mark.parametrize(
    "table,trigger",
    [
        ("approval_events", "WHEN NEW.kind='human_approved'"),
        ("approval_events", "WHEN NEW.kind='simulation_executed'"),
        ("simulated_outbox", ""),
    ],
)
def test_failed_write_rolls_back_approval_effect_and_events(
    store, proposal, table, trigger
):
    card = store.create(proposal)
    with sqlite3.connect(store.path) as db:
        db.execute(
            f"CREATE TRIGGER fail_write BEFORE INSERT ON {table} {trigger} "
            "BEGIN SELECT RAISE(FAIL, 'injected disk failure'); END"
        )
    with pytest.raises(ApprovalError):
        decide(store, card)
    after = store.show(card["approval_id"])
    assert after["status"] == "pending" and after["simulation_count"] == 0
    assert after["events"] == card["events"]
    with sqlite3.connect(store.path) as db:
        db.execute("DROP TRIGGER fail_write")
    assert decide(store, card)["simulation_count"] == 1


def test_revision_is_atomic_when_log_write_fails(store, proposal):
    card = store.create(proposal)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TRIGGER fail_revision BEFORE INSERT ON approval_events "
            "WHEN NEW.kind='approval_superseded' BEGIN SELECT RAISE(FAIL, 'full'); END"
        )
    with pytest.raises(ApprovalError):
        store.revise(card["approval_id"], card["digest"], note="changed")
    assert len(store.list()["approvals"]) == 1
    assert store.show(card["approval_id"])["status"] == "pending"


def test_parallel_approvals_have_one_simulated_effect(store, proposal):
    card = store.create(proposal)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: decide(store, card), range(12)))
    assert sum(r["decision_result"] == "executed" for r in results) == 1
    assert sum(r["decision_result"] == "already_executed" for r in results) == 11
    assert store.show(card["approval_id"])["simulation_count"] == 1


@pytest.mark.parametrize("opponent", ["reject", "revise"])
def test_competing_decisions_cannot_both_win(store, proposal, opponent):
    card = store.create(proposal)

    def competing():
        if opponent == "reject":
            return decide(store, card, "reject")
        return store.revise(card["approval_id"], card["digest"], note="changed")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(decide, store, card)
        second = pool.submit(competing)
        outcomes = [first.result(), second.result()]
    state = store.show(card["approval_id"])
    assert state["status"] in {"executed", "rejected", "superseded"}
    if state["status"] == "executed":
        assert len(store.list()["approvals"]) == 1 and state["simulation_count"] == 1
    else:
        assert state["simulation_count"] == 0
    assert sum(r["decision_result"] == "not_pending" for r in outcomes) == 1


@pytest.mark.parametrize("ttl", [0, -1, 86401, True, 1.5, "10"])
def test_invalid_ttl_cannot_create(store, proposal, ttl):
    with pytest.raises(ApprovalError):
        store.create(proposal, ttl=ttl)
    assert not store.path.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("recipient", "real-customer@example.com"),
        ("action", "send_email"),
        ("fictional", False),
        ("source_status", "failed"),
        ("answer_source", "unverified"),
        ("body", "no source"),
        ("note", "x" * 201),
        ("source_task_id", "invalid"),
        ("case", "clarification"),
        ("degraded", "false"),
    ],
)
def test_invalid_proposals_cannot_create(store, proposal, field, value):
    proposal[field] = value
    with pytest.raises(ApprovalError):
        store.create(proposal)
    assert not store.path.exists()


def test_new_task_is_separate_intent_and_digest_covers_source(store, proposal):
    first = store.create(proposal)
    proposal["source_task_id"] = "c" * 32
    second = store.create(proposal)
    assert first["digest"] != second["digest"]
    assert decide(store, first)["simulation_count"] == 1
    assert store.show(second["approval_id"])["simulation_count"] == 0


def test_same_source_with_changed_content_requires_revision(store, proposal):
    store.create(proposal)
    proposal["note"] = "changed"
    with pytest.raises(ApprovalError):
        store.create(proposal)
    assert len(store.list()["approvals"]) == 1


def test_missing_or_unrelated_database_not_created_or_modified(tmp_path):
    store = ApprovalStore(tmp_path / "missing.sqlite")
    with pytest.raises(ApprovalError):
        store.list()
    assert not store.path.exists()
    with sqlite3.connect(store.path) as db:
        db.execute("CREATE TABLE unrelated(x)")
    before = store.path.read_bytes()
    with pytest.raises(ApprovalError):
        store.initialize()
    assert store.path.read_bytes() == before


def cli(directory, *args, expected=0):
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(hitl.__file__)),
            "--data-dir",
            str(directory),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == expected, proc.stdout + proc.stderr
    return json.loads(proc.stdout)


def test_cli_create_review_approve_in_new_processes(tmp_path):
    result = cli(tmp_path, "create")
    card = result["approval"]
    assert card["simulation_count"] == 0 and card["status"] == "pending"
    assert result["generation"]["model_requests"] == 0
    before = (tmp_path / "approvals.sqlite").read_bytes()
    viewed = cli(tmp_path, "show", card["approval_id"])
    assert viewed == card
    assert len(cli(tmp_path, "list")["approvals"]) == 1
    task = cli(tmp_path, "task-log", card["proposal"]["source_task_id"])
    assert task["terminal_recorded"]
    assert (tmp_path / "approvals.sqlite").read_bytes() == before
    approved = cli(
        tmp_path,
        "approve",
        card["approval_id"],
        "--digest",
        card["digest"],
        "--confirm",
        "APPROVE",
    )
    assert approved["status"] == "executed" and approved["simulation_count"] == 1
    duplicate = cli(
        tmp_path,
        "approve",
        card["approval_id"],
        "--digest",
        card["digest"],
        "--confirm",
        "APPROVE",
    )
    assert duplicate["decision_result"] == "already_executed"


@pytest.mark.parametrize(
    "case,scenario,status,has_approval",
    [
        ("monthly", "tool_timeout_once", "completed", True),
        ("monthly", "report_timeout", "completed", True),
        ("empty", "normal", "no_data", True),
        ("monthly", "invalid_report", "rejected", False),
        ("monthly", "tool_timeout_always", "failed", False),
        ("clarification", "normal", "needs_clarification", False),
    ],
)
def test_generation_gates_approval(tmp_path, case, scenario, status, has_approval):
    result = cli(
        tmp_path,
        "create",
        "--case",
        case,
        "--scenario",
        scenario,
        expected=1 if status in ("failed", "rejected") else 0,
    )
    assert result["generation"]["status"] == status
    assert (result["approval"] is not None) is has_approval
    if has_approval:
        assert result["approval"]["simulation_count"] == 0
        if scenario == "report_timeout":
            assert result["approval"]["proposal"]["degraded"]
    else:
        assert not (tmp_path / "approvals.sqlite").exists()


def test_cli_requires_explicit_confirmation_before_mutation(tmp_path):
    for args in [
        ("approve", "unknown", "--digest", "x"),
        ("approve", "unknown", "--confirm", "APPROVE"),
    ]:
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(hitl.__file__)),
                "--data-dir",
                str(tmp_path),
                *args,
            ],
            capture_output=True,
            timeout=15,
        )
        assert proc.returncode == 2
    assert not (tmp_path / "approvals.sqlite").exists()


def test_parallel_processes_approve_one_effect(store, proposal):
    card = store.create(proposal, ttl=86400)
    # Store clock uses a future timestamp so the real CLI clock sees it unexpired.
    args = (
        "approve",
        card["approval_id"],
        "--digest",
        card["digest"],
        "--confirm",
        "APPROVE",
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: cli(store.path.parent, *args), range(4)))
    assert sum(r["decision_result"] == "executed" for r in results) == 1
    assert store.show(card["approval_id"])["simulation_count"] == 1


def test_noop_or_final_revision_cannot_create_new_approval(store, proposal):
    card = store.create(proposal)
    with pytest.raises(ApprovalError):
        store.revise(card["approval_id"], card["digest"], note="")
    decide(store, card)
    result = store.revise(card["approval_id"], card["digest"], note="changed")
    assert result["decision_result"] == "not_pending"
    assert len(store.list()["approvals"]) == 1


def test_review_digest_deterministic_and_key_order_independent(proposal):
    assert digest(proposal) == digest(dict(reversed(list(proposal.items()))))


def test_expired_revision_cannot_reset_same_approval(store, proposal, clock):
    card = store.create(proposal, ttl=1)
    clock[0] += 2
    result = store.revise(card["approval_id"], card["digest"], note="new text")
    assert result["decision_result"] == "expired"
    assert len(store.list()["approvals"]) == 1 and result["simulation_count"] == 0


def test_approval_commands_never_call_model_or_mcp(
    store, proposal, monkeypatch, capsys
):
    card = store.create(proposal)

    def forbidden(*args, **kwargs):
        pytest.fail("approval is a local transaction, not a generation step")

    monkeypatch.setattr(hitl.recovery, "run_recovery", forbidden)
    monkeypatch.setattr(hitl.agent, "Client", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hitl",
            "--data-dir",
            str(store.path.parent),
            "approve",
            card["approval_id"],
            "--digest",
            card["digest"],
            "--confirm",
            "APPROVE",
        ],
    )
    assert hitl.main() == 0
    assert json.loads(capsys.readouterr().out)["simulation_count"] == 1


def test_cli_revision_and_rejection_after_restart(store, proposal):
    card = store.create(proposal)
    new = cli(
        store.path.parent,
        "revise",
        card["approval_id"],
        "--digest",
        card["digest"],
        "--note",
        "review again",
    )
    assert new["decision_result"] == "revised" and new["status"] == "pending"
    old_attempt = cli(
        store.path.parent,
        "approve",
        card["approval_id"],
        "--digest",
        card["digest"],
        "--confirm",
        "APPROVE",
        expected=1,
    )
    assert old_attempt["status"] == "superseded"
    rejected = cli(
        store.path.parent,
        "reject",
        new["approval_id"],
        "--digest",
        new["digest"],
        "--reason",
        "needs_revision",
    )
    assert rejected["status"] == "rejected" and rejected["simulation_count"] == 0


def test_interrupted_transaction_cannot_leave_simulated_effect(store, proposal):
    card = store.create(proposal)
    code = (
        "import sqlite3,sys,os; db=sqlite3.connect(sys.argv[1]); db.execute('BEGIN IMMEDIATE'); "
        "db.execute('INSERT INTO simulated_outbox SELECT approval_id,digest,proposal,created_at FROM approvals WHERE approval_id=?',(sys.argv[2],)); "
        "db.execute(\"UPDATE approvals SET status='executed' WHERE approval_id=?\",(sys.argv[2],)); os._exit(7)"
    )
    proc = subprocess.run(
        [sys.executable, "-B", "-c", code, str(store.path), card["approval_id"]],
        capture_output=True,
        timeout=15,
    )
    assert proc.returncode == 7
    view = store.show(card["approval_id"])
    assert view["status"] == "pending" and view["simulation_count"] == 0
    assert view["events"] == card["events"]
    assert decide(store, card)["simulation_count"] == 1


@pytest.mark.parametrize("status", ["failed", "rejected", "needs_clarification"])
def test_unfinished_generation_cannot_become_proposal(status):
    with pytest.raises(ApprovalError):
        hitl.build_proposal({"status": status}, "monthly", "sales-manager-demo", "")
