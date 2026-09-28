"""Paired prompt evaluation and candidate integration with local HITL."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from prompt_policy import PROFILES, PromptChat, agent, hitl, identity

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "monthly": ("completed", 2026, 9, None, 4, "3000.00", 2, True),
    "customer": ("completed", 2026, 9, "C001", 2, "1550.00", 2, False),
    "empty": ("no_data", 2026, 7, None, 0, "0.00", 0, False),
}
FIELDS = (
    "status",
    "year",
    "month",
    "customer_id",
    "order_count",
    "total_yuan",
    "rows_returned",
    "truncated",
)
FAULTS = {
    "none",
    "no_receipt",
    "wrong_scope",
    "extra_call",
    "second_call",
    "wrong_total",
    "wrong_citation",
    "invalid_json",
    "false_fictional",
}


def save(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def load_matrix():
    matrix = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    ids = set()
    for spec in matrix:
        if (
            set(spec)
            != {
                "id",
                "case",
                "suffix",
                "fault",
                "expected_status",
                "expected_reason",
                "dispatches",
                "live",
            }
            or spec["id"] in ids
            or not spec["id"].replace("_", "").isalnum()
            or spec["case"] not in agent.CASES
            or spec["fault"] not in FAULTS
            or type(spec["live"]) is not bool
            or spec["live"] != (spec["fault"] == "none")
            or not isinstance(spec["suffix"], str)
            or type(spec["dispatches"]) is not int
            or spec["dispatches"] not in (0, 1)
            or spec["expected_status"]
            not in {"completed", "no_data", "needs_clarification", "rejected"}
        ):
            raise ValueError("invalid_prompt_matrix")
        ids.add(spec["id"])
    if not matrix:
        raise ValueError("empty_prompt_matrix")
    return matrix


class ReplayChat(agent.FixtureChat):
    """Identical scripted replies for BOTH prompts; never an accuracy model."""

    def __init__(self, spec):
        super().__init__(spec["case"])
        self.fault = spec["fault"]

    def __call__(self, messages, tools, *, tool_choice="auto"):
        reply = super().__call__(messages, tools, tool_choice=tool_choice)
        message = reply["message"]
        if tool_choice == "auto":
            if self.fault == "no_receipt":
                return {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "销售额为9999元"},
                }
            if self.fault == "wrong_scope":
                args = json.loads(message["tool_calls"][0]["function"]["arguments"])
                args["customer_id"] = "C002"
                message["tool_calls"][0]["function"]["arguments"] = json.dumps(args)
            if self.fault == "extra_call":
                extra = copy.deepcopy(message["tool_calls"][0])
                extra["id"] = "extra_call"
                message["tool_calls"].append(extra)
        else:
            if self.fault == "second_call":
                return super().__call__(messages, tools, tool_choice="auto")
            if self.fault == "invalid_json":
                message["content"] = "```json\n" + message["content"] + "\n```"
            elif self.fault in {"wrong_total", "wrong_citation", "false_fictional"}:
                report = json.loads(message["content"])
                key, value = {
                    "wrong_total": ("total_yuan", "9999.00"),
                    "wrong_citation": ("citation", "other-task/T1"),
                    "false_fictional": ("fictional", False),
                }[self.fault]
                report[key] = value
                message["content"] = json.dumps(report)
        return reply


class BudgetChat:
    """One suite-wide cap, including requests that time out. No retry here."""

    def __init__(self, chat, limit):
        self.chat, self.limit, self.attempts = chat, limit, 0

    @property
    def requests(self):
        return self.chat.requests

    @property
    def metadata(self):
        return self.chat.metadata

    def __call__(self, messages, tools, *, tool_choice="auto"):
        if self.attempts >= self.limit:
            raise agent.ToolChatError("evaluation_request_budget_exhausted")
        self.attempts += 1
        return self.chat(messages, tools, tool_choice=tool_choice)


def assess(spec, result, dispatches):
    """Independent business constants, never the agent's expected_report()."""
    errors = []
    if result["status"] != spec["expected_status"]:
        errors.append("status")
    if result["stop_reason"] != spec["expected_reason"]:
        errors.append("stop_reason")
    if result.get("database_unchanged") is not True:
        errors.append("database_changed")
    if dispatches != spec["dispatches"]:
        errors.append("tool_dispatches")
    if spec["expected_status"] in {"completed", "no_data"}:
        report = result.get("report") or {}
        values = tuple(report.get(k) for k in FIELDS)
        if values != EXPECTED[spec["case"]]:
            errors.append("business_values")
        receipt = result.get("receipt") or {}
        if report.get("citation") != receipt.get("receipt_id") or not report.get(
            "citation"
        ):
            errors.append("citation")
        if report.get("fictional") is not True:
            errors.append("fictional")
        if not result.get("answer"):
            errors.append("answer_missing")
    elif spec["expected_status"] == "rejected":
        if result.get("answer") is not None or result.get("report") is not None:
            errors.append("unsafe_answer")
    elif result.get("receipt") is not None or not result.get("answer"):
        errors.append("clarification")
    return errors


async def trial(spec, profile, database, chat, *, live=False):
    wrapped = PromptChat(chat, profile, spec["suffix"])
    transport = hitl.recovery.McpTransport(database)
    result = await agent.run_session(spec["case"], wrapped, transport, live=live)
    unchanged = hashlib.sha256(database.read_bytes()).hexdigest() == transport.snapshot
    result["database_unchanged"] = unchanged
    errors = assess(spec, result, transport.dispatches)
    return {
        "id": spec["id"],
        "prompt": wrapped.identity,
        "passed": not errors,
        "errors": errors,
        "mcp_dispatches": transport.dispatches,
        "result": result,
        "actual_model_inputs": wrapped.inputs,
    }


async def evaluate(output, *, live=False, env_file=None, selected=None):
    specs = [s for s in load_matrix() if not live or s["live"]]
    if selected:
        specs = [s for s in specs if s["id"] == selected]
    if not specs or (env_file and not live):
        raise ValueError("invalid_evaluation_selection")
    # Never overwrite evidence, even when a prior run failed or was interrupted.
    output.mkdir(parents=True, exist_ok=False)
    database = output / "fictional.sqlite"
    agent.create_demo(database)
    budget = BudgetChat(agent.ChatTools(env_file), len(specs) * 4) if live else None
    report = {
        "status": "running",
        "mode": "live_model" if live else "scripted_replay",
        "prompt_quality_comparison": "observed_sample_only" if live else "not_measured",
        "notice": "单次小样本对照，非统计结论"
        if live
        else "两版收到相同脚本回答，只验证接入和校验，不证明 Prompt 改善模型行为",
        "matrix_sha256_lf": hashlib.sha256(
            (HERE / "cases.json").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "profiles": [identity(p) for p in PROFILES],
        "request_limit": len(specs) * 4 if live else 0,
        "model_requests": 0,
        "real_messages_sent": 0,
        "results": [],
    }
    save(output / "report.json", report)
    for index, spec in enumerate(specs):
        # Alternate which prompt runs first; prompts never share chat history.
        order = PROFILES if index % 2 == 0 else tuple(reversed(PROFILES))
        for profile in order:
            record = await trial(
                spec, profile, database, budget if live else ReplayChat(spec), live=live
            )
            filename = spec["id"] + "-" + profile + ".json"
            save(output / filename, record)
            report["results"].append(
                {
                    "id": spec["id"],
                    "profile": profile,
                    "passed": record["passed"],
                    "errors": record["errors"],
                    "status": record["result"]["status"],
                    "stop_reason": record["result"]["stop_reason"],
                    "model_requests": record["result"]["model_requests"],
                    "mcp_dispatches": record["mcp_dispatches"],
                    "trace": filename,
                }
            )
            report["model_requests"] = sum(
                r["model_requests"] for r in report["results"]
            )
            save(output / "report.json", report)
            print(
                f"{spec['id']} / {profile}: {'passed' if record['passed'] else 'failed'}",
                flush=True,
            )
    report["summary"] = {
        profile: {
            "cases": len(specs),
            "passed": sum(
                r["passed"] for r in report["results"] if r["profile"] == profile
            ),
            "unexpected_results": sum(
                not r["passed"] for r in report["results"] if r["profile"] == profile
            ),
        }
        for profile in PROFILES
    }
    report["status"] = (
        "passed" if all(r["passed"] for r in report["results"]) else "failed"
    )
    save(output / "report.json", report)
    return report


async def prepare(output, case, scenario="normal"):
    """Exercise the candidate inside logs/recovery/approval; never approve."""
    if case not in agent.CASES or scenario not in hitl.recovery.SCENARIOS:
        raise ValueError("invalid_prepare_selection")
    output.mkdir(parents=True, exist_ok=False)
    database = output / "fictional.sqlite"
    agent.create_demo(database)
    wrapped = PromptChat(hitl.recovery.ScenarioChat(case, scenario), "candidate")
    result = await hitl.recovery.run_recovery(
        case,
        hitl.recovery.TaskLog(output / "tasks.sqlite"),
        hitl.recovery.McpTransport(database),
        wrapped,
        scenario=scenario,
    )
    approval = None
    if result["status"] in {"completed", "no_data"}:
        proposal = hitl.build_proposal(
            result, case, "sales-manager-demo", "Day 82 candidate"
        )
        approval = hitl.ApprovalStore(output / "approvals.sqlite").create(
            proposal, ttl=1800
        )
    trace = {
        "prompt": wrapped.identity,
        "generation": result,
        "approval": approval,
        "actual_model_inputs": wrapped.inputs,
        "external_send": False,
    }
    save(output / "generation.json", trace)
    return trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    compare = sub.add_parser("evaluate")
    compare.add_argument("--output-dir", type=Path, required=True)
    compare.add_argument("--case-id")
    compare.add_argument("--live", action="store_true")
    compare.add_argument("--env-file", type=Path)
    create = sub.add_parser("prepare")
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--case", choices=agent.CASES, default="monthly")
    create.add_argument("--scenario", choices=hitl.recovery.SCENARIOS, default="normal")
    args = parser.parse_args()
    if args.command == "list":
        print(json.dumps(load_matrix(), ensure_ascii=False, indent=2))
        return 0
    try:

        async def run():
            if args.command == "evaluate":
                return await evaluate(
                    args.output_dir,
                    live=args.live,
                    env_file=args.env_file,
                    selected=args.case_id,
                )
            return await prepare(args.output_dir, args.case, args.scenario)

        result = agent.anyio.run(run)
        if args.command == "prepare":
            print(
                json.dumps(
                    {k: v for k, v in result.items() if k != "actual_model_inputs"},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(result["generation"]["status"] in {"failed", "rejected"})
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        return int(result["status"] != "passed")
    except (OSError, ValueError, hitl.ApprovalError, hitl.recovery.JournalError):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "prompt_lab_failed",
                    "notice": "Inspect existing evidence; use a new output directory.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
