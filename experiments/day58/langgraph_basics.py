"""Run a real LangGraph with fixed planning and simulated knowledge results."""

import argparse
import json
import operator
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "demo/agent-center/day57-task-walkthrough.json"
CASES = ("success", "missing-input", "empty-result", "tool-error", "budget-limit")


class Observation(TypedDict):
    step_id: str
    outcome: Literal["ok", "empty", "error"]
    evidence_ids: list[str]


class DemoState(TypedDict):
    question: str
    scenario: str
    max_attempts: int
    attempts: int
    plan: list[str]
    next_step: int
    evidence: dict[str, dict[str, str]]
    status: str
    stop_reason: str
    answer: str
    unresolved_steps: list[str]
    completed_steps: Annotated[list[str], operator.add]
    observations: Annotated[list[Observation], operator.add]
    trace: Annotated[list[str], operator.add]


def prepare(state: DemoState) -> dict:
    """This fixed two-step plan is teaching data, not model-generated planning."""
    if not state["question"].strip():
        return {
            "status": "waiting_for_input",
            "stop_reason": "missing_question",
            "trace": ["prepare"],
        }
    return {"plan": ["S1", "S2"], "status": "running", "trace": ["prepare"]}


def mock_lookup(state: DemoState) -> dict:
    """Return fixture IDs; do not search Chroma or execute external tools."""
    step_id = state["plan"][state["next_step"]]
    outcome = "ok"
    evidence_ids = ["E1", "E2", "E3"] if step_id == "S1" else ["E4"]
    if step_id == "S2" and state["scenario"] == "empty-result":
        outcome, evidence_ids = "empty", []
    elif step_id == "S2" and state["scenario"] == "tool-error":
        outcome, evidence_ids = "error", []
    return {
        "attempts": state["attempts"] + 1,
        "observations": [
            {"step_id": step_id, "outcome": outcome, "evidence_ids": evidence_ids}
        ],
        "trace": ["mock_lookup"],
    }


def evaluate(state: DemoState) -> dict:
    observation = state["observations"][-1]
    update = {"trace": ["evaluate"]}
    if observation["outcome"] == "error":
        return {**update, "status": "failed", "stop_reason": "mock_tool_error"}
    if not observation["evidence_ids"]:
        return {**update, "status": "incomplete", "stop_reason": "missing_evidence"}
    return {
        **update,
        "completed_steps": [observation["step_id"]],
        "next_step": state["next_step"] + 1,
    }


def route_next(state: DemoState) -> Literal["lookup", "finish"]:
    """The same guard runs before the first lookup and after each evaluation."""
    if (
        state["status"] != "running"
        or state["next_step"] >= len(state["plan"])
        or state["attempts"] >= state["max_attempts"]
    ):
        return "finish"
    return "lookup"


def finish(state: DemoState) -> dict:
    status, reason = state["status"], state["stop_reason"]
    unresolved = [
        step for step in state["plan"] if step not in state["completed_steps"]
    ]
    if status == "running":
        status = "incomplete" if unresolved else "succeeded"
        reason = "attempt_budget_exhausted" if unresolved else "all_steps_supported"
    lines = []
    for observation in state["observations"]:
        for evidence_id in observation["evidence_ids"]:
            item = state["evidence"][evidence_id]
            lines.append(f"{item['text']} [{item['source']} / {evidence_id}]")
    if "S2" in state["completed_steps"]:
        lines.append("8000 元属于超过 3000 元但不超过 10000 元的审批区间。")
    if status == "waiting_for_input":
        lines.append("请补充要处理的问题；本实验只演示预设的制度问答任务。")
    elif unresolved:
        lines.append("未完成步骤：" + ", ".join(unresolved))
    return {
        "status": status,
        "stop_reason": reason,
        "answer": "\n".join(lines),
        "unresolved_steps": unresolved,
        "trace": ["finish"],
    }


def build_graph():
    builder = StateGraph(DemoState)
    builder.add_node("prepare", prepare)
    builder.add_node("mock_lookup", mock_lookup)
    builder.add_node("evaluate", evaluate)
    builder.add_node("finish", finish)
    builder.add_edge(START, "prepare")
    targets = {"lookup": "mock_lookup", "finish": "finish"}
    builder.add_conditional_edges("prepare", route_next, targets)
    builder.add_edge("mock_lookup", "evaluate")
    builder.add_conditional_edges("evaluate", route_next, targets)
    builder.add_edge("finish", END)
    return builder.compile()


def initial_state(scenario: str) -> DemoState:
    if scenario not in CASES:
        raise ValueError(f"Unknown scenario: {scenario}")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {
        "question": ""
        if scenario == "missing-input"
        else fixture["task"]["user_request"],
        "scenario": scenario,
        "max_attempts": 1 if scenario == "budget-limit" else 2,
        "attempts": 0,
        "plan": [],
        "next_step": 0,
        "evidence": {item["evidence_id"]: item for item in fixture["fixture_evidence"]},
        "status": "pending",
        "stop_reason": "",
        "answer": "",
        "unresolved_steps": [],
        "completed_steps": [],
        "observations": [],
        "trace": [],
    }


def run_case(scenario: str) -> dict:
    # Explicitly disable hosted tracing, even if enabled in the caller's environment.
    with tracing_context(enabled=False):
        state = build_graph().invoke(initial_state(scenario), {"recursion_limit": 12})
    return {
        "artifact_type": "executed_graph_with_mock_nodes",
        "graph_executed": True,
        "model_called": False,
        "external_tool_called": False,
        "persistent_state": False,
        "scenario": scenario,
        "state": state,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=(*CASES, "all"), default="success")
    parser.add_argument(
        "--mermaid", action="store_true", help="Print graph source locally"
    )
    args = parser.parse_args()
    if args.mermaid:
        print(build_graph().get_graph().draw_mermaid())
        return
    results = (
        [run_case(name) for name in CASES]
        if args.case == "all"
        else run_case(args.case)
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
