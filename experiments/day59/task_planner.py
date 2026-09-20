"""Day 59: model-generated plans with local schema validation, no task execution."""

import argparse
import json
import operator
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chat_planner import ChatPlanner, PlanningError  # noqa: E402
from plan_schema import parse_plan  # noqa: E402

DEMO_GOAL = "请制定计划：查明星云科技 P1 故障的响应和升级流程，以及单笔 8000 元差旅报销需要哪些人审批。只规划，不执行。"


class PlannerState(TypedDict):
    goal: str
    status: str
    stop_reason: str
    raw_output: str
    plan: dict | None
    questions: list[str]
    planning_attempts: int
    trace: Annotated[list[str], operator.add]


def validate_input(state: PlannerState) -> dict:
    goal = state["goal"]
    if not isinstance(goal, str) or len(goal) > 2000:
        return {
            "status": "failed",
            "stop_reason": "invalid_goal",
            "trace": ["validate_input"],
        }
    if not goal.strip():
        return {
            "status": "waiting_for_input",
            "stop_reason": "missing_goal",
            "questions": ["请说明要处理的任务和希望得到的结果。"],
            "trace": ["validate_input"],
        }
    return {"goal": goal.strip(), "status": "running", "trace": ["validate_input"]}


def validate_plan(state: PlannerState) -> dict:
    try:
        decision = parse_plan(state["raw_output"])
    except (ValueError, TypeError, RecursionError):
        return {
            "status": "failed",
            "stop_reason": "invalid_model_output",
            "trace": ["validate_plan"],
        }
    if decision.decision == "clarify":
        return {
            "status": "waiting_for_input",
            "stop_reason": "model_requests_clarification",
            "questions": decision.questions,
            "trace": ["validate_plan"],
        }
    return {
        "status": "planned",
        "stop_reason": "plan_validated",
        "plan": decision.model_dump(),
        "trace": ["validate_plan"],
    }


def build_graph(generate):
    def generate_plan(state: PlannerState) -> dict:
        update = {"planning_attempts": 1, "trace": ["generate_plan"]}
        try:
            return {**update, "raw_output": generate(state["goal"])}
        except PlanningError as exc:
            return {**update, "status": "failed", "stop_reason": exc.code}

    def after_input(state):
        return "generate_plan" if state["status"] == "running" else "finish"

    def after_generation(state):
        return "validate_plan" if state["status"] == "running" else "finish"

    def finish(state):
        # Invalid raw content is not exposed in the public result or stored on disk.
        return {"raw_output": "", "trace": ["finish"]}

    builder = StateGraph(PlannerState)
    for name, node in (
        ("validate_input", validate_input),
        ("generate_plan", generate_plan),
        ("validate_plan", validate_plan),
        ("finish", finish),
    ):
        builder.add_node(name, node)
    builder.add_edge(START, "validate_input")
    builder.add_conditional_edges(
        "validate_input", after_input, ["generate_plan", "finish"]
    )
    builder.add_conditional_edges(
        "generate_plan", after_generation, ["validate_plan", "finish"]
    )
    builder.add_edge("validate_plan", "finish")
    builder.add_edge("finish", END)
    return builder.compile()


def run_task(goal: str, generate, *, mode: str) -> dict:
    requests_before = getattr(generate, "requests", 0)
    with tracing_context(enabled=False):
        state = build_graph(generate).invoke(
            {
                "goal": goal,
                "status": "pending",
                "stop_reason": "",
                "raw_output": "",
                "plan": None,
                "questions": [],
                "planning_attempts": 0,
                "trace": [],
            },
            {"recursion_limit": 8},
        )
    state.pop("raw_output")
    return {
        "artifact_type": "task_planning_result",
        "mode": mode,
        "task_executed": False,
        "tools_executed": False,
        "persistent_state": False,
        "model_requests": getattr(generate, "requests", 0) - requests_before,
        "model": getattr(generate, "metadata", {}),
        "state": state,
    }


def mock_generator(case: str):
    cases = json.loads(
        (Path(__file__).with_name("mock-responses.json")).read_text(encoding="utf-8")
    )
    if case not in cases:
        raise ValueError("Unknown mock case")

    def generate(goal):
        if case == "provider-error":
            raise PlanningError("provider_timeout")
        value = cases[case]
        return (
            json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value
        )

    return generate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--live", action="store_true", help="Call the configured model once"
    )
    mode.add_argument(
        "--mock-case", choices=("normal", "clarify", "invalid", "provider-error")
    )
    parser.add_argument("--goal")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.live and args.goal is None:
        parser.error("--live requires --goal")
    if args.env_file is not None and not args.live:
        parser.error("--env-file only applies to --live")
    if args.live:
        generate = ChatPlanner(args.env_file)
    else:
        generate = mock_generator(args.mock_case or "normal")
    goal = args.goal if args.goal is not None else DEMO_GOAL
    result = run_task(goal, generate, mode="live" if args.live else "mock")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["state"]["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
