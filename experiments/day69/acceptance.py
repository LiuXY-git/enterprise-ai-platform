"""Repeatable complex-task acceptance, deterministic delivery and fresh-run recovery."""

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day68"))
from briefing import render_briefing  # noqa: E402
from multi_tool_agent import (  # noqa: E402
    ChatTools,
    FixtureChat,
    ToolChatError,
    run_session,
)
from tool_registry import (  # noqa: E402
    KNOWLEDGE,
    SQL,
    WEATHER,
    knowledge,
    make_registry,
    sales,
    scope_for,
    weather,
)

SCENARIOS = json.loads(
    Path(__file__).with_name("scenarios.json").read_text(encoding="utf-8")
)
BY_ID = {row["id"]: row for row in SCENARIOS}


def tool_reply(name, params, call_id):
    return {
        "finish_reason": "tool_calls",
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(params)},
                }
            ],
        },
    }


class ScenarioChat:
    requests = 0
    metadata = {}

    def __init__(self, scenario):
        self.scenario = scenario
        self.fixture = FixtureChat(
            scenario["base"], weather_first=scenario.get("weather_first", False)
        )
        self.turn = 0

    def __call__(self, messages, tools, *, tool_choice):
        self.turn += 1
        scenario = self.scenario
        if self.turn == scenario.get("fault_turn"):
            fault = scenario["fault"]
            if fault == "model_timeout":
                raise ToolChatError("provider_timeout")
            if fault == "repeat_sql":
                return tool_reply(SQL, scope_for("full")["sales"], "repeated")
            if fault == "extra_call":
                return tool_reply(WEATHER, scope_for("full")["weather"], "extra")
            if fault == "injection":
                return tool_reply("delete_all_files", {}, "injected")
            if fault == "premature_report":
                return {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "done"},
                }
        reply = self.fixture(messages, tools, tool_choice=tool_choice)
        if self.turn != scenario.get("fault_turn"):
            return reply
        fault = scenario["fault"]
        if fault == "duplicate_id":
            reply["message"]["tool_calls"][0]["id"] = "call_1"
        elif fault == "batch":
            other = copy.deepcopy(reply["message"]["tool_calls"][0])
            other["id"] = "parallel"
            reply["message"]["tool_calls"].append(other)
        elif fault == "wrong_scope":
            reply["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps(
                {"year": 2025, "month": 9, "customer_id": None, "limit": 2}
            )
        elif fault == "bad_citation":
            report = json.loads(reply["message"]["content"])
            report["citations"] = ["T99"]
            report["summary"] = "Unsupported[T99]"
            reply["message"]["content"] = json.dumps(report)
        return reply


def build_registry(database, scenario, *, live=False):
    if live and scenario["id"] not in {"no_sales", "weather_timeout"}:
        raise ValueError("live_case_not_supported")
    registry = make_registry(database, "full" if live else scenario["base"], live=live)
    registry.scope = scope_for(scenario["base"])
    if live and scenario["id"] == "weather_timeout":
        registry.bindings[WEATHER] = weather.fixture_tool(failure="timeout")
    if scenario.get("fault") == "knowledge_timeout":

        class Unavailable:
            def query(self, params):
                raise knowledge.KnowledgeError("retrieval_timeout")

        registry.bindings[KNOWLEDGE] = Unavailable()
    if scenario.get("fault") == "injection":
        registry.bindings[KNOWLEDGE] = knowledge.KnowledgeTool(
            knowledge.FixtureRetriever("injection")
        )
    return registry


def check_outcome(result, scenario):
    checks = {
        "status": result["status"] == scenario["expected_status"],
        "stop_reason": result["stop_reason"] == scenario["expected_stop"],
        "tool_attempts": result["tool_attempts"] == scenario["attempts"],
        "tool_executions": result["tool_executions"] == scenario["successes"],
        "model_turn_budget": result["chat_turns"] <= 4,
        "tool_budget": result["tool_attempts"] <= 3,
        "no_business_action": result["external_business_actions"] is False,
    }
    return {"passed": all(checks.values()), "checks": checks}


def run_case(case, database, *, live=False, env_file=None):
    scenario = BY_ID[case]
    registry = build_registry(database, scenario, live=live)
    scope = registry.scope
    goal = f"查询虚构销售库{scope['sales']['year']}年{scope['sales']['month']}月全部客户的已支付销售额和订单数，明细最多2条。有已支付订单时，再查询虚构酒店报销上限、发票要求和上海从当地今天开始1天的天气；没有订单就跳过。独立工具失败也要保留已有信息，明确未完成项。"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = run_session(
        goal,
        ChatTools(env_file) if live else ScenarioChat(scenario),
        registry,
        mode="live_model" if live else "fixture",
    )
    after = hashlib.sha256(database.read_bytes()).hexdigest()
    delivery = render_briefing(result, "day69-" + uuid.uuid4().hex)
    verdict = check_outcome(result, scenario)
    verdict["checks"]["database_unchanged"] = before == after
    verdict["passed"] = all(verdict["checks"].values())
    return {
        "case": case,
        "verification_mode": "live_model_with_injected_failure"
        if live and case == "weather_timeout"
        else "live_model"
        if live
        else "offline",
        "weather_failure_is_simulated": case
        in {"weather_timeout", "weather_first_timeout", "both_fail"},
        "database_sha256_before": before,
        "database_sha256_after": after,
        "verdict": verdict,
        "result": result,
        "delivery": delivery,
    }


def recovery_pair(database):
    first = run_case("weather_timeout", database)
    second = run_case("full", database)
    return {
        "mode": "two_fresh_offline_sessions",
        "resume_supported": False,
        "first": first,
        "second": second,
        "passed": first["verdict"]["passed"]
        and second["verdict"]["passed"]
        and first["delivery"]["run_id"] != second["delivery"]["run_id"]
        and first["result"]["tool_attempts"] == second["result"]["tool_attempts"] == 3
        and first["database_sha256_before"] == second["database_sha256_after"],
    }


def historical_delivery():
    directory = ROOT / "docs/evidence/day68"
    raw = (directory / "live-full.json").read_bytes()
    expected = json.loads((directory / "validation.json").read_text(encoding="utf-8"))[
        "evidence_hashes"
    ]["live-full.json"]
    actual = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    if actual != expected:
        raise ValueError("historical_evidence_hash_mismatch")
    record = json.loads(raw)
    return {
        "mode": "historical_render_only",
        "new_model_requests": 0,
        "new_api_requests": 0,
        "historical_evidence_sha256": actual,
        "recorded_at_utc": record["recorded_at_utc"],
        "delivery": render_briefing(record["result"], "day68-historical-snapshot"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--case", choices=list(BY_ID))
    group.add_argument("--check-all", action="store_true")
    group.add_argument("--recovery-check", action="store_true")
    group.add_argument("--render-day68", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()
    if args.live and args.case not in {"weather_timeout", "no_sales"}:
        parser.error("--live requires --case weather_timeout or no_sales")
    if args.env_file is not None and not args.live:
        parser.error("--env-file requires --live")
    if args.markdown and (args.check_all or args.recovery_check):
        parser.error("--markdown requires a single case or --render-day68")
    if args.render_day68:
        value = historical_delivery()
        print(
            value["delivery"]["markdown"]
            if args.markdown
            else json.dumps(value, ensure_ascii=False, indent=2)
        )
        return 0
    with tempfile.TemporaryDirectory(prefix="day69-fictional-") as directory:
        database = Path(directory) / "sales.sqlite"
        sales.create_demo(database)
        if args.recovery_check:
            value = recovery_pair(database)
            passed = value["passed"]
        elif args.check_all:
            cases = [run_case(case, database) for case in BY_ID]
            value = {
                "cases": cases,
                "passed": all(row["verdict"]["passed"] for row in cases),
            }
            passed = value["passed"]
        else:
            value = run_case(
                args.case or "full", database, live=args.live, env_file=args.env_file
            )
            passed = value["verdict"]["passed"]
    print(
        value["delivery"]["markdown"]
        if args.markdown
        else json.dumps(value, ensure_ascii=False, indent=2)
    )
    # This is an acceptance runner: expected failures also pass the acceptance check.
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
