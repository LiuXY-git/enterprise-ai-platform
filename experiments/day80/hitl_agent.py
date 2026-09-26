"""Generate a fixed fictional brief, then wait for local human approval."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from approval_store import (
    REASONS,
    RECIPIENTS,
    ApprovalError,
    ApprovalStore,
    validate_proposal,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day79"))
import recovery_agent as recovery  # noqa: E402

agent = recovery.agent


def build_proposal(result, case, recipient, note):
    if (
        result["status"] not in ("completed", "no_data")
        or result.get("database_unchanged") is not True
        or result.get("tool_execution_outcome") != "success"
    ):
        raise ApprovalError("generation_not_eligible")
    return validate_proposal(
        {
            "action": "simulate_send_sales_brief",
            "recipient": recipient,
            "body": result["answer"],
            "note": note,
            "case": case,
            "source_task_id": result["task_id"],
            "agent_run_id": result["agent_run_id"],
            "source_status": result["status"],
            "answer_source": result["answer_source"],
            "degraded": result["degraded"],
            "fictional": True,
        }
    )


async def prepare(data_dir, case, scenario, recipient, note, ttl):
    # Validate local input before any model or MCP operation.
    ApprovalStore.validate_ttl(ttl)
    if recipient not in RECIPIENTS or not isinstance(note, str) or len(note) > 200:
        raise ApprovalError("invalid_proposal")
    logs = recovery.TaskLog(data_dir / "tasks.sqlite")
    with tempfile.TemporaryDirectory(prefix="day80-fictional-") as directory:
        database = Path(directory) / "sales.sqlite"
        agent.create_demo(database)
        result = await recovery.run_recovery(
            case,
            logs,
            recovery.McpTransport(database),
            recovery.ScenarioChat(case, scenario),
            scenario=scenario,
        )
    if result["status"] not in ("completed", "no_data"):
        return {"generation": result, "approval": None, "external_send": False}
    proposal = build_proposal(result, case, recipient, note)
    approval = ApprovalStore(data_dir / "approvals.sqlite").create(proposal, ttl=ttl)
    return {"generation": result, "approval": approval, "external_send": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/day80")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--case", choices=agent.CASES, default="monthly")
    create.add_argument("--scenario", choices=recovery.SCENARIOS, default="normal")
    create.add_argument("--recipient", choices=RECIPIENTS, default=RECIPIENTS[0])
    create.add_argument("--note", default="")
    create.add_argument("--ttl-seconds", type=int, default=1800)
    commands.add_parser("list")
    show = commands.add_parser("show")
    show.add_argument("approval_id")
    task = commands.add_parser("task-log")
    task.add_argument("task_id")
    approve = commands.add_parser("approve")
    approve.add_argument("approval_id")
    approve.add_argument("--digest", required=True)
    approve.add_argument("--confirm", choices=["APPROVE"], required=True)
    reject = commands.add_parser("reject")
    reject.add_argument("approval_id")
    reject.add_argument("--digest", required=True)
    reject.add_argument("--reason", choices=REASONS, default="not_needed")
    revise = commands.add_parser("revise")
    revise.add_argument("approval_id")
    revise.add_argument("--digest", required=True)
    revise.add_argument("--recipient", choices=RECIPIENTS)
    revise.add_argument("--note")
    revise.add_argument("--ttl-seconds", type=int, default=1800)
    args = parser.parse_args()
    try:
        store = ApprovalStore(args.data_dir / "approvals.sqlite")
        if args.command == "create":

            async def run():
                return await prepare(
                    args.data_dir,
                    args.case,
                    args.scenario,
                    args.recipient,
                    args.note,
                    args.ttl_seconds,
                )

            result = agent.anyio.run(run)
            code = 1 if result["generation"]["status"] in ("failed", "rejected") else 0
        elif args.command == "task-log":
            result = recovery.read_log(args.data_dir / "tasks.sqlite", args.task_id)
            code = 0
        elif args.command == "list":
            result, code = store.list(), 0
        elif args.command == "show":
            result, code = store.show(args.approval_id), 0
        elif args.command == "revise":
            result = store.revise(
                args.approval_id,
                args.digest,
                recipient=args.recipient,
                note=args.note,
                ttl=args.ttl_seconds,
            )
            code = 0 if result["decision_result"] == "revised" else 1
        else:
            result = store.decide(
                args.approval_id,
                args.digest,
                args.command,
                reason=getattr(args, "reason", "not_needed"),
            )
            code = (
                0
                if result["decision_result"]
                in ("executed", "already_executed", "rejected")
                else 1
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (ApprovalError, recovery.JournalError, OSError, ValueError):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "approval_or_log_operation_failed",
                    "notice": "Inspect the saved approval before retrying; no external send exists.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
