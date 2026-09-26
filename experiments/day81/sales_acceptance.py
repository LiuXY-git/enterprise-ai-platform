"""Independent business oracles and cross-process acceptance of Days 78-80."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = Path(__file__).with_name("scenarios.json")
HITL = ROOT / "experiments/day80/hitl_agent.py"
ACTIONS = {
    "approve",
    "none",
    "reject",
    "revise",
    "expire",
    "duplicate",
    "cross_task",
    "parallel",
}
FAULTS = {
    "normal",
    "tool_timeout_once",
    "tool_timeout_always",
    "report_timeout",
    "invalid_report",
    "invalid_arguments",
}
SCOPES = {
    "monthly": {"year": 2026, "month": 9, "customer_id": None, "limit": 2},
    "customer": {"year": 2026, "month": 9, "customer_id": "C001", "limit": 5},
    "empty": {"year": 2026, "month": 7, "customer_id": None, "limit": 5},
    "clarification": None,
}


class AcceptanceError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise AcceptanceError(code)


def load_matrix(path=MATRIX):
    body = json.loads(path.read_text(encoding="utf-8"))
    require(set(body) == {"version", "data_kind", "scenarios"}, "invalid_matrix")
    require(
        body["version"] == 1 and body["data_kind"] == "fictional_fixed_sales",
        "invalid_matrix",
    )
    scenarios = body["scenarios"]
    require(isinstance(scenarios, list) and 1 <= len(scenarios) <= 30, "invalid_matrix")
    ids = set()
    for item in scenarios:
        require(
            set(item) == {"id", "goal", "case", "fault", "action", "expected"},
            "invalid_scenario",
        )
        require(
            isinstance(item["id"], str)
            and re.fullmatch(r"[a-z][a-z0-9_]{0,60}", item["id"]),
            "invalid_id",
        )
        require(item["id"] not in ids, "duplicate_scenario")
        ids.add(item["id"])
        require(
            item["case"] in SCOPES
            and item["fault"] in FAULTS
            and item["action"] in ACTIONS,
            "unknown_operation",
        )
        require(
            isinstance(item["goal"], str) and 0 < len(item["goal"]) <= 300,
            "invalid_goal",
        )
        expected = item["expected"]
        require(
            set(expected)
            == {"status", "total_yuan", "order_count", "dispatches", "degraded"},
            "invalid_expectation",
        )
        require(
            expected["status"]
            in {"completed", "no_data", "needs_clarification", "failed", "rejected"},
            "invalid_expectation",
        )
        require(
            type(expected["dispatches"]) is int and 0 <= expected["dispatches"] <= 2,
            "invalid_expectation",
        )
        require(type(expected["degraded"]) is bool, "invalid_expectation")
        eligible = expected["status"] in {"completed", "no_data"}
        require(eligible == (item["action"] != "none"), "invalid_action_for_status")
        if eligible:
            require(
                isinstance(expected["total_yuan"], str)
                and re.fullmatch(r"[0-9]+\.[0-9]{2}", expected["total_yuan"]),
                "invalid_expectation",
            )
            require(
                type(expected["order_count"]) is int and expected["order_count"] >= 0,
                "invalid_expectation",
            )
        else:
            require(
                expected["total_yuan"] is None and expected["order_count"] is None,
                "invalid_expectation",
            )
    return scenarios


def content_digest(proposal):
    encoded = json.dumps(
        proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def check_generation(spec, created, replay):
    """Do not call the production render/expected_report functions as the oracle."""
    result, card = created["generation"], created["approval"]
    expected = spec["expected"]
    require(created["external_send"] is False, "external_send_detected")
    for key in ("status", "degraded"):
        require(result[key] == expected[key], "generation_" + key + "_mismatch")
    require(
        result["mcp_dispatches"] == expected["dispatches"], "dispatch_count_mismatch"
    )
    require(
        result["model_requests"] == 0 and result["database_unchanged"] is True,
        "unsafe_generation",
    )
    require(
        0 <= result["model_attempts"] <= 4 and 0 <= result["tool_attempts"] <= 2,
        "budget_exceeded",
    )
    require(replay["read_only"] and replay["terminal_recorded"], "incomplete_task_log")
    require(replay["task"]["task_id"] == result["task_id"], "wrong_task_log")
    events = replay["events"]
    require(events[-1]["kind"] == "final_answer", "missing_final_event")
    require(
        events[-1]["payload"] == {k: v for k, v in result.items() if k != "task_id"},
        "result_log_mismatch",
    )
    calls = [
        e["payload"]
        for e in events
        if e["kind"] == "tool_call" and e["payload"].get("phase") == "attempt"
    ]
    require(len(calls) == result["tool_attempts"], "attempt_log_mismatch")
    require(
        all(call["arguments"] == SCOPES[spec["case"]] for call in calls),
        "query_scope_mismatch",
    )
    eligible = expected["status"] in {"completed", "no_data"}
    require((card is not None) == eligible, "approval_eligibility_mismatch")
    if not eligible:
        if expected["status"] != "needs_clarification":
            require(result["answer"] is None, "failed_generation_has_answer")
        return
    receipts = [e["payload"] for e in events if e["kind"] == "tool_result"]
    require(len(receipts) == 1, "missing_validated_result")
    receipt = receipts[0]
    require(
        receipt["total_yuan"] == expected["total_yuan"]
        and receipt["order_count"] == expected["order_count"],
        "business_total_mismatch",
    )
    require(
        receipt["fictional"] is True and receipt["validated"] is True,
        "unverified_result",
    )
    require(
        receipt["rows_returned"]
        == min(expected["order_count"], SCOPES[spec["case"]]["limit"]),
        "detail_count_mismatch",
    )
    require(
        receipt["truncated"]
        == (expected["order_count"] > SCOPES[spec["case"]]["limit"]),
        "truncation_mismatch",
    )
    answer = result["answer"]
    require(
        isinstance(answer, str)
        and expected["total_yuan"] in answer
        and "教学虚构数据" in answer,
        "answer_business_mismatch",
    )
    require(result["agent_run_id"] + "/T1" in answer, "citation_mismatch")
    scope = SCOPES[spec["case"]]
    require(
        f"2026年{scope['month']}月" in answer
        and (scope["customer_id"] or "所有客户") in answer,
        "answer_scope_mismatch",
    )
    if expected["order_count"]:
        require(
            f"已支付订单{expected['order_count']}条" in answer,
            "answer_order_count_mismatch",
        )
    else:
        require("没有已支付订单" in answer, "no_data_claim_mismatch")
    require(
        card["status"] == "pending"
        and card["simulation_count"] == 0
        and card["external_send"] is False,
        "execution_before_approval",
    )
    proposal = card["proposal"]
    require(
        proposal["source_task_id"] == result["task_id"]
        and proposal["agent_run_id"] == result["agent_run_id"],
        "proposal_source_mismatch",
    )
    require(
        proposal["body"] == answer and proposal["case"] == spec["case"],
        "proposal_content_mismatch",
    )
    require(
        proposal["recipient"] == "sales-manager-demo" and proposal["fictional"] is True,
        "proposal_scope_mismatch",
    )
    require(
        proposal["degraded"] == result["degraded"]
        and proposal["answer_source"] == result["answer_source"],
        "fallback_label_mismatch",
    )
    require(card["digest"] == content_digest(proposal), "proposal_digest_mismatch")
    if expected["degraded"]:
        require(
            result["answer_source"] == "validated_receipt_fallback"
            and "本地模板" in answer,
            "fallback_label_missing",
        )


def audit_database(path):
    if not path.exists():
        return {"approvals": [], "outbox": [], "events": []}
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        return {
            key: [dict(row) for row in db.execute(query)]
            for key, query in {
                "approvals": "SELECT * FROM approvals ORDER BY source_task_id, revision",
                "outbox": "SELECT * FROM simulated_outbox ORDER BY approval_id",
                "events": "SELECT * FROM approval_events ORDER BY approval_id, seq",
            }.items()
        }


def check_audit(audit, expected_count):
    require(len(audit["outbox"]) == expected_count, "simulated_effect_count_mismatch")
    approvals = {row["approval_id"]: row for row in audit["approvals"]}
    outbox = {row["approval_id"]: row for row in audit["outbox"]}
    require(len(outbox) == len(audit["outbox"]), "duplicate_effect")
    for key, row in approvals.items():
        require(
            (row["status"] == "executed") == (key in outbox), "state_effect_mismatch"
        )
        require(
            row["digest"] == content_digest(json.loads(row["proposal"])),
            "stored_digest_mismatch",
        )
    for key, effect in outbox.items():
        require(key in approvals, "orphan_effect")
        row = approvals[key]
        require(
            effect["proposal"] == row["proposal"] and effect["digest"] == row["digest"],
            "executed_content_mismatch",
        )
        events = [e for e in audit["events"] if e["approval_id"] == key]
        approved = [e for e in events if e["kind"] == "human_approved"]
        executed = [e for e in events if e["kind"] == "simulation_executed"]
        require(len(approved) == len(executed) == 1, "missing_unique_approval")
        require(approved[0]["seq"] < executed[0]["seq"], "execution_before_approval")
        require(
            json.loads(approved[0]["details"])["digest"] == effect["digest"],
            "approved_content_mismatch",
        )
        require(
            json.loads(executed[0]["details"])["external_send"] is False,
            "external_send_detected",
        )


class Commands:
    def __init__(self, directory):
        self.directory = directory
        self.history = []

    def call(self, args, expected=0):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run(
            [sys.executable, "-B", str(HITL), "--data-dir", str(self.directory), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=60,
        )
        try:
            response = json.loads(proc.stdout)
        except ValueError:
            self.history.append(
                {
                    "args": args,
                    "exit_code": proc.returncode,
                    "response": "non_json_output",
                }
            )
            raise AcceptanceError("invalid_cli_output") from None
        self.history.append(
            {"args": args, "exit_code": proc.returncode, "response": response}
        )
        require(proc.returncode == expected, "unexpected_cli_exit")
        return response

    def decide(self, card, command="approve", *, expected=0, extra=()):
        args = [command, card["approval_id"], "--digest", card["digest"]]
        if command == "approve":
            args += ["--confirm", "APPROVE"]
        return self.call(args + list(extra), expected)


def run_scenario(spec, directory):
    directory.mkdir()
    commands = Commands(directory / "data")
    trace = {
        "scenario": spec,
        "decisions": "automated_test_driver_local_simulation_only",
    }
    outcome = {
        "id": spec["id"],
        "status": "failed",
        "trace": spec["id"] + "/trace.json",
    }
    try:
        args = ["create", "--case", spec["case"], "--scenario", spec["fault"]]
        if spec["action"] == "expire":
            args += ["--ttl-seconds", "1"]
        created = commands.call(
            args, 1 if spec["expected"]["status"] in {"failed", "rejected"} else 0
        )
        generation, card = created["generation"], created["approval"]
        before = (commands.directory / "tasks.sqlite").read_bytes()
        replay = commands.call(["task-log", generation["task_id"]])
        require(
            (commands.directory / "tasks.sqlite").read_bytes() == before,
            "task_replay_mutated_data",
        )
        check_generation(spec, created, replay)
        trace["generation"] = generation
        initial_audit = audit_database(commands.directory / "approvals.sqlite")
        check_audit(initial_audit, 0)
        require(
            [r["status"] for r in initial_audit["approvals"]]
            == (["pending"] if card else []),
            "initial_approval_state_mismatch",
        )
        trace["initial_audit"] = initial_audit
        action = spec["action"]
        if card is not None:
            before = (commands.directory / "approvals.sqlite").read_bytes()
            reviewed = commands.call(["show", card["approval_id"]])
            require(
                reviewed["proposal"] == card["proposal"]
                and reviewed["digest"] == card["digest"],
                "review_mismatch",
            )
            require(
                (commands.directory / "approvals.sqlite").read_bytes() == before,
                "review_mutated_data",
            )
        if action == "approve":
            require(
                commands.decide(card)["decision_result"] == "executed",
                "approval_did_not_execute",
            )
        elif action == "reject":
            require(
                commands.decide(card, "reject")["status"] == "rejected",
                "rejection_failed",
            )
            require(
                commands.decide(card, expected=1)["decision_result"] == "not_pending",
                "rejected_task_executed",
            )
        elif action == "revise":
            revised = commands.decide(
                card,
                "revise",
                extra=["--recipient", "finance-demo", "--note", "复核虚构销售简报"],
            )
            require(
                revised["status"] == "pending"
                and revised["simulation_count"] == 0
                and revised["digest"] != card["digest"],
                "revision_not_pending",
            )
            require(
                commands.decide(card, expected=1)["status"] == "superseded",
                "old_version_executed",
            )
            stale = dict(revised, digest=card["digest"])
            require(
                commands.decide(stale, expected=1)["decision_result"]
                == "digest_mismatch",
                "stale_digest_accepted",
            )
            require(
                commands.decide(revised)["status"] == "executed",
                "revision_not_executed",
            )
        elif action == "expire":
            time.sleep(1.1)
            require(
                commands.decide(card, expected=1)["status"] == "expired",
                "expired_task_executed",
            )
        elif action == "duplicate":
            require(
                commands.decide(card)["decision_result"] == "executed",
                "approval_did_not_execute",
            )
            require(
                commands.decide(card)["decision_result"] == "already_executed",
                "duplicate_not_idempotent",
            )
        elif action == "cross_task":
            other_spec = dict(
                spec,
                case="customer",
                expected={
                    "status": "completed",
                    "total_yuan": "1550.00",
                    "order_count": 2,
                    "dispatches": 1,
                    "degraded": False,
                },
            )
            other = commands.call(["create", "--case", "customer"])
            other_replay = commands.call(["task-log", other["generation"]["task_id"]])
            check_generation(other_spec, other, other_replay)
            require(
                other["generation"]["task_id"] != generation["task_id"],
                "task_id_reused",
            )
            wrong = dict(other["approval"], digest=card["digest"])
            require(
                commands.decide(wrong, expected=1)["decision_result"]
                == "digest_mismatch",
                "cross_task_approval_accepted",
            )
            require(
                commands.decide(other["approval"])["status"] == "executed",
                "customer_approval_failed",
            )
            require(
                commands.call(["show", card["approval_id"]])["status"] == "pending",
                "other_task_changed",
            )
            trace["secondary_generation"] = other["generation"]
        elif action == "parallel":
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(lambda _: commands.decide(card), range(3)))
            require(
                sum(r["decision_result"] == "executed" for r in results) == 1,
                "parallel_duplicate_execution",
            )
            require(
                sum(r["decision_result"] == "already_executed" for r in results) == 2,
                "parallel_result_mismatch",
            )
        audit = audit_database(commands.directory / "approvals.sqlite")
        trace["audit"] = audit
        expected_effects = 0 if action in {"none", "reject", "expire"} else 1
        check_audit(audit, expected_effects)
        terminal_states = {
            "approve": ["executed"],
            "duplicate": ["executed"],
            "parallel": ["executed"],
            "reject": ["rejected"],
            "expire": ["expired"],
            "none": [],
        }
        if action in terminal_states:
            require(
                sorted(row["status"] for row in audit["approvals"])
                == terminal_states[action],
                "persisted_approval_state_mismatch",
            )
        if action == "none":
            require(not audit["approvals"], "failed_generation_created_approval")
        if action == "revise":
            require(
                sorted(row["status"] for row in audit["approvals"])
                == ["executed", "superseded"],
                "revision_state_mismatch",
            )
        if action == "cross_task":
            require(
                sorted(row["status"] for row in audit["approvals"])
                == ["executed", "pending"],
                "cross_task_state_mismatch",
            )
        total_dispatches = generation["mcp_dispatches"] + trace.get(
            "secondary_generation", {}
        ).get("mcp_dispatches", 0)
        outcome.update(
            status="passed",
            generation_status=generation["status"],
            simulated_effects=expected_effects,
            real_mcp_dispatches=total_dispatches,
            model_requests=0,
        )
    except AcceptanceError as exc:
        outcome["error"] = str(exc)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        sqlite3.Error,
        subprocess.TimeoutExpired,
    ):
        outcome["error"] = "scenario_execution_error"
    finally:
        trace["commands"] = commands.history
        trace["outcome"] = outcome
        (directory / "trace.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return outcome


def run_suite(output, scenarios):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for spec in scenarios:
        result = run_scenario(spec, output / spec["id"])
        results.append(result)
        print(f"{spec['id']}: {result['status']}", file=sys.stderr, flush=True)
    passed = sum(r["status"] == "passed" for r in results)
    report = {
        "status": "passed" if passed == len(scenarios) and scenarios else "failed",
        "scope": "fixed_fictional_sales_with_recovery_and_simulated_human_decisions",
        "scenario_count": len(scenarios),
        "passed": passed,
        "failed": len(scenarios) - passed,
        "model_requests": 0,
        "real_messages_sent": 0,
        "matrix_sha256": hashlib.sha256(
            MATRIX.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "results": results,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    scenarios = load_matrix()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--scenario", choices=[s["id"] for s in scenarios] + ["all"], default="all"
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.list:
        print(json.dumps(scenarios, ensure_ascii=False, indent=2))
        return 0
    if args.output_dir is None:
        parser.error("--output-dir requires a new directory")
    chosen = (
        scenarios
        if args.scenario == "all"
        else [s for s in scenarios if s["id"] == args.scenario]
    )
    try:
        report = run_suite(args.output_dir, chosen)
    except OSError:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "output_directory_must_be_new_and_writable",
                }
            )
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
