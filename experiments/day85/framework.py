"""Validate evaluation inputs and write a non-executing plan. Never run Agent."""

import argparse
import hashlib
import json
from pathlib import Path

from contracts import (
    AgentSpec,
    Dataset,
    EvaluationPlan,
    PlannedResult,
    PlanSummary,
    canonical_hash,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = Path(__file__).resolve().parent / "examples"
MAX_INPUT_BYTES = 1_048_576


def unique_object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate_json_key")
        output[key] = value
    return output


def reject_constant(_):
    raise ValueError("non_finite_json_number")


def load_contract(path, model):
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input_too_large")
    parsed = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )
    return model.model_validate(parsed)


def verify_sources(agent, root=ROOT):
    root = Path(root).resolve()
    for name, expected in agent.source_sha256_lf.items():
        path = root / name
        if not path.resolve().is_relative_to(root) or any(
            p.is_symlink() for p in [path, *path.parents] if p != root
        ):
            raise ValueError("source_path_escapes_repository")
        actual = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != expected:
            raise ValueError("agent_source_hash_mismatch")


def make_plan(agent, dataset, root=ROOT):
    verify_sources(agent, root)
    return EvaluationPlan(
        schema_version="0.1-design",
        report_kind="preflight_plan_not_evaluation",
        execution_status="not_run",
        agent=agent,
        dataset=dataset,
        agent_spec_sha256=canonical_hash(agent.model_dump()),
        dataset_sha256=canonical_hash(dataset.model_dump()),
        identity_check="declared_local_files_only_commit_not_resolved",
        rows=[PlannedResult(case_id=c.case_id) for c in dataset.cases],
        summary=PlanSummary(total_cases=len(dataset.cases), not_run=len(dataset.cases)),
    )


def save(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def preview(agent_path, dataset_path, output, root=ROOT):
    agent = load_contract(agent_path, AgentSpec)
    dataset = load_contract(dataset_path, Dataset)
    plan = make_plan(agent, dataset, root)
    output.mkdir(parents=True, exist_ok=False)
    save(output / "report.json", plan.model_dump())
    return plan


def export_schemas(output):
    output.mkdir(parents=True, exist_ok=False)
    for name, model in (
        ("agent", AgentSpec),
        ("dataset", Dataset),
        ("plan-report", EvaluationPlan),
    ):
        save(output / (name + ".schema.json"), model.model_json_schema())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--kind", choices=["agent", "dataset", "report"], required=True)
    check.add_argument("--file", type=Path, required=True)
    plan = sub.add_parser("preview")
    plan.add_argument("--agent", type=Path, default=EXAMPLES / "agent.json")
    plan.add_argument("--dataset", type=Path, default=EXAMPLES / "dataset.json")
    plan.add_argument("--output-dir", type=Path, required=True)
    schemas = sub.add_parser("schemas")
    schemas.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "check":
            model = {"agent": AgentSpec, "dataset": Dataset, "report": EvaluationPlan}[
                args.kind
            ]
            load_contract(args.file, model)
            result = {
                "status": "contract_valid",
                "local_source_hashes_checked": False,
                "agent_executed": False,
            }
        elif args.command == "preview":
            report = preview(args.agent, args.dataset, args.output_dir)
            result = {
                "status": "preflight_valid",
                "execution_status": report.execution_status,
                "cases": report.summary.total_cases,
                "report": str(args.output_dir / "report.json"),
                "local_source_hashes_checked": True,
                "agent_executed": False,
            }
        else:
            export_schemas(args.output_dir)
            result = {"status": "schemas_exported", "agent_executed": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        # Do not echo untrusted input, credentials or full Pydantic error values.
        code = (
            "invalid_contract"
            if isinstance(exc, ValidationError)
            else "input_or_output_invalid"
        )
        print(json.dumps({"status": "failed", "error": code, "agent_executed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
