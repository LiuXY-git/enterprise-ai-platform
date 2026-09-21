"""Day 62: model report generation followed by schema and evidence verification."""

import argparse
import json
from pathlib import Path

from chat_report import ChatReport, ReportError
from prompt_builder import PROMPT_VERSION, build_messages, prompt_hash, system_prompt
from report_contract import ROOT, ScenarioInput, parse_decision, verify_decision


def load_cases() -> list[dict]:
    return json.loads(
        (ROOT / "experiments/day61/cases.json").read_text(encoding="utf-8")
    )["cases"]


def fixture_response(case: dict) -> str:
    # Offline plumbing check only: these authored expectations never enter live messages.
    expected = case["expected"]
    return json.dumps(
        {
            key: expected[key]
            for key in ("scope", "status", "missing_fields", "recommendations", "gaps")
        },
        ensure_ascii=False,
    )


def run_report(input_data: dict, generate, *, mode: str) -> dict:
    result = {
        "artifact_type": "sales_prompt_result",
        "mode": mode,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash(),
        "verification": "rejected",
        "stop_reason": "invalid_input",
        "report": None,
        "generation_attempts": 0,
        "model_requests": 0,
        "model": {},
        "business_actions_executed": False,
        "persistent_state": False,
    }
    try:
        source = ScenarioInput.model_validate(input_data)
    except (ValueError, TypeError, RecursionError):
        return result
    try:
        messages = build_messages(source)
    except ValueError:
        result["stop_reason"] = "input_too_large"
        return result
    requests_before = getattr(generate, "requests", 0)
    result["generation_attempts"] = 1
    try:
        raw = generate(messages)
    except ReportError as exc:
        result["stop_reason"] = exc.code
        return result
    finally:
        result["model_requests"] = getattr(generate, "requests", 0) - requests_before
        result["model"] = dict(getattr(generate, "metadata", {}))
    try:
        decision = parse_decision(raw)
    except (ValueError, TypeError, RecursionError):
        result["stop_reason"] = "invalid_model_output"
        return result
    try:
        verify_decision(source, decision)
    except (ValueError, TypeError, RecursionError):
        result["stop_reason"] = "evidence_mismatch"
        return result
    result.update(
        verification="accepted",
        stop_reason="report_validated",
        report=decision.model_dump(),
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument(
        "--live",
        action="store_true",
        help="One configured-model request for one fictional case",
    )
    operations.add_argument(
        "--check-all",
        action="store_true",
        help="Offline fixtures only; not a model evaluation",
    )
    operations.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.env_file is not None and not args.live:
        parser.error("--env-file only applies to --live")
    if args.live and not args.case:
        parser.error("--live requires an explicit --case")
    if args.case and (args.check_all or args.show_prompt):
        parser.error("--case cannot be combined with --check-all or --show-prompt")
    if args.show_prompt:
        print(system_prompt())
        return 0
    cases = load_cases()
    selected = (
        cases
        if args.check_all
        else [case for case in cases if case["id"] == (args.case or "normal")]
    )
    if not selected:
        print(json.dumps({"error": "unknown_case"}))
        return 1
    results = []
    for case in selected:
        generate = (
            ChatReport(args.env_file)
            if args.live
            else lambda messages, case=case: fixture_response(case)
        )
        result = run_report(
            case["input"], generate, mode="live" if args.live else "fixture"
        )
        results.append({"case": case["id"], "result": result})
    print(
        json.dumps(
            results if args.check_all else results[0], ensure_ascii=False, indent=2
        )
    )
    return (
        0
        if all(item["result"]["verification"] == "accepted" for item in results)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
