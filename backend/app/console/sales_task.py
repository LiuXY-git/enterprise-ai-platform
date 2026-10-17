"""Fixed fixture sales adapter, executed only in the isolated Linux worker."""

import argparse
import json
import sys
from pathlib import Path

from .contracts import SalesResult

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        choices=("monthly", "customer", "empty", "clarification"),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "experiments/day82"))
    import prompt_lab

    async def prepare():
        return await prompt_lab.prepare(args.output_dir, args.case, "normal")

    trace = prompt_lab.agent.anyio.run(prepare)
    generation = trace["generation"]
    log = prompt_lab.hitl.recovery.read_log(
        args.output_dir / "tasks.sqlite", generation["task_id"]
    )
    if (
        not log["terminal_recorded"]
        or not generation["database_unchanged"]
        or generation["model_requests"] != 0
        or trace["external_send"]
    ):
        raise ValueError("sales_validation_failed")
    receipt = None
    for turn in trace["actual_model_inputs"]:
        for message in turn["messages"]:
            if message["role"] == "tool":
                receipt = json.loads(message["content"])
    report = (
        prompt_lab.agent.expected_report(
            receipt, prompt_lab.agent.CASES[args.case]["scope"]
        )
        if receipt
        else None
    )
    sources = {"task_id": generation["task_id"], "run_id": generation["agent_run_id"]}
    if trace["approval"]:
        sources["approval_id"] = trace["approval"]["approval_id"]
    result = SalesResult(
        case=args.case,
        mode="fixture",
        business_status=generation["status"],
        answer=generation["answer"],
        source_ids=sources,
        report=report,
        receipt=receipt,
        events=log["events"],
        model_requests=0,
        external_send=False,
    )
    (args.output_dir / "web-result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
