"""Fixed fixture-only child adapter. It never receives golden answers or arbitrary code."""

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day86.dataset_contracts import REQUIRED_PAIRS  # noqa: E402
from experiments.day86.dataset_tool import save  # noqa: E402
from experiments.day87.execution_contracts import (  # noqa: E402
    Observations,
    WorkerResult,
)


def collect(trace, journal, artifacts):
    generation = trace["generation"]
    if (
        not journal["terminal_recorded"]
        or journal["task"]["task_id"] != generation["task_id"]
    ):
        raise ValueError("journal_task_mismatch")
    final = journal["events"][-1]
    if (
        final["kind"] != "final_answer"
        or final["payload"]["status"] != generation["status"]
    ):
        raise ValueError("journal_terminal_mismatch")
    approval = trace["approval"]
    approval_db = artifacts / "approvals.sqlite"
    effects = 0
    if approval_db.exists():
        with closing(
            sqlite3.connect(approval_db.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            effects = db.execute("SELECT COUNT(*) FROM simulated_outbox").fetchone()[0]
    elif approval is not None:
        raise ValueError("missing_approval_database")
    fields = [
        "task_id",
        "agent_run_id",
        "stop_reason",
        "answer",
        "answer_source",
        "tool_attempts",
        "mcp_dispatches",
        "tool_retries",
        "model_attempts",
        "model_retries",
        "model_requests",
        "degraded",
        "database_unchanged",
    ]
    return Observations(
        business_status=generation["status"],
        **{k: generation[k] for k in fields},
        approval_status=approval["status"] if approval else None,
        simulated_effects=effects,
        external_send=trace["external_send"],
        event_count=len(journal["events"]),
    )


def execute(case_id, case, scenario, output):
    if (case, scenario) not in REQUIRED_PAIRS:
        raise ValueError("unsupported_case")
    # Only this fixed fixture entry is imported, after input validation.
    sys.path.insert(0, str(ROOT / "experiments/day82"))
    import prompt_lab

    artifacts = output / "artifacts"

    async def run():
        return await prompt_lab.prepare(artifacts, case, scenario)

    trace = prompt_lab.agent.anyio.run(run)
    journal = prompt_lab.hitl.recovery.read_log(
        artifacts / "tasks.sqlite", trace["generation"]["task_id"]
    )
    save(artifacts / "events.json", journal)
    observed = collect(trace, journal, artifacts)
    result = WorkerResult(
        protocol="day87-worker-v1",
        case_id=case_id,
        case=case,
        scenario=scenario,
        observations=observed,
    )
    save(output / "worker-result.json", result.model_dump())
    # A recorded business failure/rejection is a completed execution, not a worker crash.
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--case",
        required=True,
        choices=["monthly", "customer", "empty", "clarification"],
    )
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        return execute(args.case_id, args.case, args.scenario, args.output_dir)
    except Exception:
        print(json.dumps({"error": "fixture_worker_failed"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
