"""Offline evidence tests; never interpret scripted replay as model quality."""

import copy
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompt_lab as lab  # noqa: E402
from prompt_policy import PromptChat, identity, prompt_text  # noqa: E402

SPECS = lab.load_matrix()


@pytest.fixture(scope="module")
def paired(tmp_path_factory):
    output = tmp_path_factory.mktemp("day82") / "paired"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(lab.__file__)),
            "evaluate",
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    return output, report


@pytest.mark.parametrize("profile", lab.PROFILES)
@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s["id"])
def test_paired_controls(paired, profile, spec):
    output, report = paired
    summary = next(
        r
        for r in report["results"]
        if r["id"] == spec["id"] and r["profile"] == profile
    )
    trace = json.loads((output / summary["trace"]).read_text(encoding="utf-8"))
    assert summary["passed"] and trace["passed"]
    assert trace["prompt"] == identity(profile)
    assert trace["result"]["database_unchanged"] is True
    assert trace["mcp_dispatches"] == spec["dispatches"]
    assert trace["result"]["model_requests"] == 0
    for request in trace["actual_model_inputs"]:
        assert request["messages"][0]["content"] == prompt_text(profile)
        assert (
            request["messages"][1]["content"]
            == lab.agent.CASES[spec["case"]]["goal"] + spec["suffix"]
        )
    if spec["expected_status"] == "rejected":
        assert trace["result"]["answer"] is None


def test_replay_has_no_quality_claim(paired):
    _, report = paired
    assert report["status"] == "passed"
    assert report["mode"] == "scripted_replay"
    assert report["prompt_quality_comparison"] == "not_measured"
    assert (
        report["model_requests"]
        == report["request_limit"]
        == report["real_messages_sent"]
        == 0
    )
    assert len(report["results"]) == 32
    assert report["summary"]["baseline"] == report["summary"]["candidate"]


@pytest.mark.parametrize(
    "mutation",
    ["amount", "customer", "citation", "fictional", "database", "dispatch", "status"],
)
def test_oracle_detects_wrong_result(paired, mutation):
    output, _ = paired
    trace = json.loads((output / "monthly-candidate.json").read_text(encoding="utf-8"))
    result = trace["result"]
    dispatches = 1
    if mutation == "amount":
        result["report"]["total_yuan"] = "9999.00"
    elif mutation == "customer":
        result["report"]["customer_id"] = "C001"
    elif mutation == "citation":
        result["report"]["citation"] = "another/T1"
    elif mutation == "fictional":
        result["report"]["fictional"] = False
    elif mutation == "database":
        result["database_unchanged"] = False
    elif mutation == "dispatch":
        dispatches = 2
    else:
        result["status"] = "failed"
    assert lab.assess(SPECS[0], result, dispatches)


def test_wrapper_preserves_contract_and_records_real_input():
    messages = [
        {"role": "system", "content": lab.agent.SYSTEM},
        {"role": "user", "content": "query"},
    ]
    tools = [{"name": "fixed"}]
    before = copy.deepcopy((messages, tools))
    returned = {"opaque": "reply"}

    def chat(sent, definitions, *, tool_choice):
        assert sent[0]["content"] == prompt_text("candidate")
        assert sent[1]["content"] == "query suffix"
        assert definitions == tools and tool_choice == "none"
        sent[0]["content"] = "mutated by downstream"
        definitions.clear()
        return returned

    wrapper = PromptChat(chat, "candidate", " suffix")
    assert wrapper(messages, tools, tool_choice="none") is returned
    assert (messages, tools) == before
    assert wrapper.inputs[0]["messages"][0]["content"] == prompt_text("candidate")


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": "x"}],
        [{"role": "system", "content": "unexpected"}, {"role": "user", "content": "x"}],
    ],
)
def test_wrapper_rejects_changed_host_contract(messages):
    def forbidden(*args, **kwargs):
        pytest.fail("must not call downstream")

    with pytest.raises(lab.agent.ToolChatError, match="prompt_contract_invalid"):
        PromptChat(forbidden, "candidate")(messages, [])


def test_live_budget_includes_failed_requests():
    class TimeoutChat:
        requests = 0
        metadata = {}

        def __call__(self, *args, **kwargs):
            self.requests += 1
            raise lab.agent.ToolChatError("provider_timeout")

    budget = lab.BudgetChat(TimeoutChat(), 2)
    for _ in range(2):
        with pytest.raises(lab.agent.ToolChatError, match="provider_timeout"):
            budget([], [])
    with pytest.raises(
        lab.agent.ToolChatError, match="evaluation_request_budget_exhausted"
    ):
        budget([], [])
    assert budget.attempts == budget.requests == 2


@pytest.mark.parametrize(
    "case,scenario,status,approval",
    [
        ("monthly", "normal", "completed", True),
        ("customer", "normal", "completed", True),
        ("empty", "normal", "no_data", True),
        ("clarification", "normal", "needs_clarification", False),
        ("monthly", "tool_timeout_once", "completed", True),
        ("monthly", "tool_timeout_always", "failed", False),
        ("monthly", "report_timeout", "completed", True),
        ("monthly", "invalid_report", "rejected", False),
        ("monthly", "invalid_arguments", "rejected", False),
    ],
)
def test_candidate_logs_recovery_and_waits_for_approval(
    tmp_path, case, scenario, status, approval
):
    output = tmp_path / "candidate"

    async def run():
        return await lab.prepare(output, case, scenario)

    result = lab.agent.anyio.run(run)
    assert result["prompt"] == identity("candidate")
    assert result["generation"]["status"] == status
    assert result["generation"]["model_requests"] == 0
    assert result["generation"]["degraded"] == (scenario == "report_timeout")
    assert result["external_send"] is False
    assert (result["approval"] is not None) == approval
    saved = json.loads((output / "generation.json").read_text(encoding="utf-8"))
    assert saved == result
    if approval:
        assert result["approval"]["status"] == "pending"
        with sqlite3.connect(output / "approvals.sqlite") as db:
            assert (
                db.execute("SELECT COUNT(*) FROM simulated_outbox").fetchone()[0] == 0
            )
    else:
        assert not (output / "approvals.sqlite").exists()
    for request in result["actual_model_inputs"]:
        assert request["messages"][0]["content"] == prompt_text("candidate")


@pytest.mark.parametrize("command", ["evaluate", "prepare"])
def test_preserves_existing_directory(tmp_path, command):
    marker = tmp_path / "keep.txt"
    marker.write_text("unchanged")

    async def run():
        if command == "evaluate":
            return await lab.evaluate(tmp_path)
        return await lab.prepare(tmp_path, "monthly")

    with pytest.raises(FileExistsError):
        lab.agent.anyio.run(run)
    assert list(tmp_path.iterdir()) == [marker] and marker.read_text() == "unchanged"


@pytest.mark.parametrize(
    "live,selected,env",
    [
        (False, "missing", None),
        (True, "reject_wrong_total", None),
        (False, None, Path("unused.env")),
    ],
)
def test_invalid_selection_before_output_or_network(tmp_path, live, selected, env):
    output = tmp_path / "not_created"

    async def run():
        return await lab.evaluate(output, live=live, selected=selected, env_file=env)

    with pytest.raises(ValueError):
        lab.agent.anyio.run(run)
    assert not output.exists()


def test_live_orchestration_with_transport_double(tmp_path, monkeypatch):
    # This tests selection/counting only, never claims a live provider request.
    async def fake_trial(spec, profile, database, chat, *, live=False):
        assert live and spec["live"] and isinstance(chat, lab.BudgetChat)
        return {
            "id": spec["id"],
            "prompt": identity(profile),
            "passed": profile == "candidate",
            "errors": [] if profile == "candidate" else ["status"],
            "mcp_dispatches": 0,
            "result": {
                "status": "completed",
                "stop_reason": "report_verified",
                "model_requests": 2,
            },
        }

    monkeypatch.setattr(lab, "trial", fake_trial)

    async def run():
        return await lab.evaluate(tmp_path / "double", live=True)

    report = lab.agent.anyio.run(run)
    assert len(report["results"]) == 16
    assert report["model_requests"] == report["request_limit"] == 32
    assert report["status"] == "failed"
    assert report["summary"]["baseline"]["passed"] == 0
    assert report["summary"]["candidate"]["passed"] == 8
