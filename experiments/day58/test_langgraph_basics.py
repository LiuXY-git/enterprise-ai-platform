"""Exercise the actual compiled graph with deterministic fixture responses."""

import copy
import socket

import pytest

pytest.importorskip(
    "langgraph", reason="Install experiments/day58/requirements-lock.txt"
)

from langgraph.errors import GraphRecursionError  # noqa: E402
from langgraph_basics import build_graph, initial_state, run_case  # noqa: E402
from langsmith import tracing_context  # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("The Day 58 experiment must not access the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.mark.parametrize(
    ("scenario", "status", "reason", "attempts", "completed", "unresolved"),
    [
        ("success", "succeeded", "all_steps_supported", 2, ["S1", "S2"], []),
        ("missing-input", "waiting_for_input", "missing_question", 0, [], []),
        ("empty-result", "incomplete", "missing_evidence", 2, ["S1"], ["S2"]),
        ("tool-error", "failed", "mock_tool_error", 2, ["S1"], ["S2"]),
        ("budget-limit", "incomplete", "attempt_budget_exhausted", 1, ["S1"], ["S2"]),
    ],
)
def test_terminal_branch(scenario, status, reason, attempts, completed, unresolved):
    result = run_case(scenario)
    state = result["state"]
    assert state["status"] == status
    assert state["stop_reason"] == reason
    assert state["attempts"] == attempts
    assert state["completed_steps"] == completed
    assert state["unresolved_steps"] == unresolved
    assert state["trace"] == ["prepare"] + ["mock_lookup", "evaluate"] * attempts + [
        "finish"
    ]
    assert len(state["observations"]) == attempts
    assert result["graph_executed"] is True
    assert result["model_called"] is False
    assert result["external_tool_called"] is False
    assert result["persistent_state"] is False


def test_success_answer_is_supported_by_original_fixture_sources():
    state = run_case("success")["state"]
    assert "15 分钟" in state["answer"]
    assert "30 分钟仍未得到响应" in state["answer"]
    assert "直属部门负责人和财务负责人共同审批" in state["answer"]
    assert "业务副总裁" not in state["answer"]
    assert "demo/nebula-it-policy.md" in state["answer"]
    assert "demo/nebula-expense-policy.md" in state["answer"]


@pytest.mark.parametrize("scenario", ["empty-result", "tool-error", "budget-limit"])
def test_partial_results_do_not_invent_expense_answer(scenario):
    state = run_case(scenario)["state"]
    assert "15 分钟" in state["answer"]
    assert "E4" not in state["answer"]
    assert "财务负责人" not in state["answer"]
    assert "未完成步骤：S2" in state["answer"]


def test_zero_budget_never_calls_lookup():
    state = initial_state("success")
    state["max_attempts"] = 0
    with tracing_context(enabled=False):
        result = build_graph().invoke(state)
    assert result["attempts"] == 0
    assert result["observations"] == []
    assert result["trace"] == ["prepare", "finish"]
    assert result["status"] == "incomplete"
    assert result["unresolved_steps"] == ["S1", "S2"]


def test_compiled_graph_does_not_share_progress_between_invocations():
    graph = build_graph()
    state = initial_state("success")
    original = copy.deepcopy(state)
    with tracing_context(enabled=False):
        first = graph.invoke(state)
        second = graph.invoke(state)
    assert first == second
    assert state == original
    assert len(second["completed_steps"]) == 2
    assert len(second["observations"]) == 2


def test_recursion_limit_is_a_graph_guard_not_business_success():
    with tracing_context(enabled=False), pytest.raises(GraphRecursionError):
        build_graph().invoke(initial_state("success"), {"recursion_limit": 1})


def test_hosted_tracing_stays_disabled_when_environment_enables_it(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    assert run_case("success")["state"]["status"] == "succeeded"


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError, match="Unknown scenario"):
        run_case("unregistered")
