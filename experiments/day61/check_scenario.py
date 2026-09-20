"""Validate a bundled fictional sales case; never query CRM or invoke a model."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError
from sales_contract import SalesReport, ScenarioInput
from scenario_rules import assess, validate_report

CASES = Path(__file__).with_name("cases.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="normal")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--check-all", action="store_true")
    args = parser.parse_args()
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if args.list:
        print(json.dumps([case["id"] for case in cases], indent=2))
        return 0
    selected = cases if args.check_all else [c for c in cases if c["id"] == args.case]
    if not selected:
        print(json.dumps({"error": "unknown_case"}))
        return 1
    summaries = []
    try:
        for case in selected:
            source = ScenarioInput.model_validate(case["input"])
            expected = SalesReport.model_validate(case["expected"])
            validate_report(source, expected)
            result = assess(source)
            summaries.append({"case": case["id"], "status": result.status})
    except (ValidationError, ValueError):
        print(json.dumps({"error": "fixture_contract_mismatch"}))
        return 1
    if args.check_all:
        output = {
            "validation": "passed",
            "cases": summaries,
            "model_requests": 0,
            "business_actions_executed": False,
        }
    else:
        output = {
            "case": selected[0]["id"],
            "validation": "passed",
            "report": result.model_dump(),
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    # A checked failed-source fixture is a successful contract check, not business success.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
