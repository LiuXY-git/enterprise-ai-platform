"""A checkpointed simulation of plan progress; no model or business tools."""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class ProgressState(TypedDict):
    task_id: str
    plan: dict
    cursor: int
    status: str
    simulated_steps: Annotated[list[str], operator.add]
    trace: Annotated[list[str], operator.add]


def pause_step(state: ProgressState) -> dict:
    step = state["plan"]["steps"][state["cursor"]]
    # This node restarts on resume. Keep everything before interrupt side-effect free.
    interrupt({"kind": "simulation_step", "step_id": step["id"]})
    return {"status": "running", "trace": [f"resume:{step['id']}"]}


def simulate_step(state: ProgressState) -> dict:
    step = state["plan"]["steps"][state["cursor"]]
    if not set(step["depends_on"]) <= set(state["simulated_steps"]):
        return {"status": "failed", "trace": ["invalid_dependencies"]}
    # A progress marker only: never execute descriptions, URLs or generated code.
    return {
        "cursor": state["cursor"] + 1,
        "simulated_steps": [step["id"]],
        "trace": [f"simulate:{step['id']}"],
    }


def after_step(state: ProgressState) -> str:
    if state["status"] == "failed" or state["cursor"] == len(state["plan"]["steps"]):
        return "finish"
    return "pause_step"


def finish(state: ProgressState) -> dict:
    return {
        "status": "failed" if state["status"] == "failed" else "simulation_completed",
        "trace": ["finish"],
    }


def build_graph(checkpointer):
    builder = StateGraph(ProgressState)
    builder.add_node("pause_step", pause_step)
    builder.add_node("simulate_step", simulate_step)
    builder.add_node("finish", finish)
    builder.add_edge(START, "pause_step")
    builder.add_edge("pause_step", "simulate_step")
    builder.add_conditional_edges("simulate_step", after_step, ["pause_step", "finish"])
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=checkpointer)
