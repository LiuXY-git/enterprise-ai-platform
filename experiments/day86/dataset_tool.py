"""Validate Day 86 inputs, independent totals and coverage without running Agent."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.day85.contracts import (  # noqa: E402
    AgentSpec,
    PlannedResult,
    PlanSummary,
    canonical_hash,
)  # noqa: E402
from experiments.day86.dataset_contracts import DatasetPlan, FormalDataset  # noqa: E402

DATASET = ROOT / "evaluation-center/datasets/sales-prepare-v1.0.0.json"
AGENT = ROOT / "experiments/day85/examples/agent.json"


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError("non_finite_number")


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("input_too_large")
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def verify_hashes(hashes, root):
    root = Path(root).resolve()
    for name, expected in hashes.items():
        path = root / name
        if not path.resolve().is_relative_to(root) or any(
            p.is_symlink() for p in [path, *path.parents] if p != root
        ):
            raise ValueError("source_path_invalid")
        if (
            hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            != expected
        ):
            raise ValueError("source_hash_mismatch")


def verify_oracle(dataset, root=ROOT):
    """Independent integer arithmetic over raw fixture, never imports production SQL/report code."""
    verify_hashes(dataset.source_sha256_lf, root)
    source = read_json(Path(root) / "experiments/day65/sales-data.json")
    if source["fictional"] is not True or source["currency"] != "CNY":
        raise ValueError("fixture_kind_mismatch")
    for case in dataset.cases:
        g = case.golden_report
        if g is None:
            continue
        prefix = f"{g.scope.year}-{g.scope.month:02d}-"
        orders = sorted(
            [
                o
                for o in source["orders"]
                if o["status"] == "paid"
                and o["order_date"].startswith(prefix)
                and (
                    g.scope.customer_id is None
                    or o["customer_id"] == g.scope.customer_id
                )
            ],
            key=lambda o: (o["order_date"], o["order_id"]),
        )
        if g.matched_order_ids != [o["order_id"] for o in orders] or (
            g.total_cents != sum(o["amount_cents"] for o in orders)
        ):
            raise ValueError("independent_order_oracle_mismatch")


def load_dataset(path=DATASET, root=ROOT):
    dataset = FormalDataset.model_validate(read_json(path))
    verify_oracle(dataset, root)
    return dataset


def make_plan(dataset, agent, suite="full", root=ROOT):
    verify_oracle(dataset, root)
    verify_hashes(agent.source_sha256_lf, root)
    ids = (
        dataset.smoke_case_ids
        if suite == "smoke"
        else [c.case_id for c in dataset.cases]
    )
    return DatasetPlan(
        schema_version="1.0-dataset",
        report_kind="preflight_plan_not_evaluation",
        execution_status="not_run",
        agent=agent,
        dataset=dataset,
        agent_spec_sha256=canonical_hash(agent.model_dump()),
        dataset_sha256=canonical_hash(dataset.model_dump()),
        suite=suite,
        identity_check="local_source_hashes_only_commit_not_resolved",
        rows=[PlannedResult(case_id=key) for key in ids],
        summary=PlanSummary(total_cases=len(ids), not_run=len(ids)),
    )


def save(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--dataset", type=Path, default=DATASET)
    preview = sub.add_parser("preview")
    preview.add_argument("--dataset", type=Path, default=DATASET)
    preview.add_argument("--agent", type=Path, default=AGENT)
    preview.add_argument("--suite", choices=["smoke", "full"], default="full")
    preview.add_argument("--output-dir", type=Path, required=True)
    schema = sub.add_parser("schemas")
    schema.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "schemas":
            args.output_dir.mkdir(parents=True, exist_ok=False)
            for name, model in [
                ("dataset", FormalDataset),
                ("plan-report", DatasetPlan),
            ]:
                save(
                    args.output_dir / (name + ".schema.json"), model.model_json_schema()
                )
            result = {"status": "schemas_exported"}
        else:
            dataset = load_dataset(args.dataset)
            if args.command == "check":
                result = {
                    "status": "dataset_valid",
                    "cases": len(dataset.cases),
                    "categories": dict(
                        sorted(Counter(c.category for c in dataset.cases).items())
                    ),
                    "smoke_cases": len(dataset.smoke_case_ids),
                    "local_source_hashes_checked": True,
                    "oracle_checked": True,
                    "dataset_sha256": canonical_hash(dataset.model_dump()),
                }
            else:
                agent = AgentSpec.model_validate(read_json(args.agent))
                report = make_plan(dataset, agent, args.suite)
                args.output_dir.mkdir(parents=True, exist_ok=False)
                save(args.output_dir / "report.json", report.model_dump())
                result = {
                    "status": "preflight_valid",
                    "execution_status": "not_run",
                    "cases": report.summary.total_cases,
                    "suite": args.suite,
                    "report": str(args.output_dir / "report.json"),
                }
        result["agent_executed"] = False
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "invalid_dataset_or_io",
                    "agent_executed": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
