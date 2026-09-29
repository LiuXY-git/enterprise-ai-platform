"""Fixture execution accounting and explicit offline ledger pricing; no live mode."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day85.contracts import canonical_hash  # noqa: E402
from experiments.day86.dataset_tool import read_json  # noqa: E402
from experiments.day87 import runner as files  # noqa: E402
from experiments.day88 import runner as latency  # noqa: E402
from experiments.day88.latency import TimedReport  # noqa: E402
from experiments.day89.reporting import MeteredReport, fixture_usage  # noqa: E402
from experiments.day89.usage import Attempt, Pricing, summarize  # noqa: E402

HERE = Path(__file__).resolve().parent


def load_price(path):
    return Pricing.model_validate(read_json(path)) if path else None


def run(output, *, suite="full", timeout=60, prices=None):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("existing_output")
    price = load_price(prices)
    sources = {
        p.relative_to(ROOT).as_posix(): files.digest(p, lf=True)
        for p in HERE.glob("*.py")
        if not p.name.startswith("test_")
    }
    result = latency.run(output / "execution", suite=suite, timeout=timeout)
    execution = TimedReport.model_validate(result)
    report = MeteredReport(
        schema_version="day89-usage-v1",
        report_kind="fixture_execution_with_explicit_usage_coverage",
        execution=execution,
        execution_sha256=canonical_hash(execution.model_dump()),
        pricing=price,
        pricing_sha256=canonical_hash(price.model_dump()) if price else None,
        usage=fixture_usage(execution),
        source_sha256_lf=sources,
    )
    files.atomic_save(output / "report.json", report.model_dump())
    return report


def inspect(output):
    output = Path(output).resolve()
    report = MeteredReport.model_validate(read_json(output / "report.json"))
    latency.inspect(output / "execution")
    if (
        canonical_hash(read_json(output / "execution/report.json"))
        != report.execution_sha256
    ):
        raise ValueError("nested_execution_mismatch")
    return dict(
        status="evidence_consistent",
        run_status=report.execution.run_status,
        usage=report.usage["summary"],
        agent_executed=False,
    )


def replay(ledger, prices, output):
    value = read_json(ledger)
    if not isinstance(value, list):
        raise ValueError("ledger_must_be_list")
    attempts = [Attempt.model_validate(item) for item in value]
    price = load_price(prices)
    summary = summarize(attempts, price)
    result = dict(
        schema_version="day89-ledger-estimate-v1",
        report_kind="usage_ledger_estimate_not_new_execution",
        attempts=[a.model_dump() for a in attempts],
        summary=summary,
        pricing=price.model_dump() if price else None,
        pricing_sha256=canonical_hash(price.model_dump()) if price else None,
        ledger_sha256=canonical_hash([a.model_dump() for a in attempts]),
        agent_executed=False,
        notice="supplied_usage_not_independently_verified_provider_billing",
    )
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    files.atomic_save(output / "report.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--suite", choices=["smoke", "full"], default="full")
    execute.add_argument("--timeout-seconds", type=int, default=60)
    execute.add_argument("--prices", type=Path)
    execute.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("inspect")
    check.add_argument("--output-dir", type=Path, required=True)
    calculate = sub.add_parser("replay")
    calculate.add_argument("--ledger", type=Path, required=True)
    calculate.add_argument("--prices", type=Path)
    calculate.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        code = 0
        if args.command == "run":
            report = run(
                args.output_dir,
                suite=args.suite,
                timeout=args.timeout_seconds,
                prices=args.prices,
            )
            result = dict(
                run_status=report.execution.run_status, usage=report.usage["summary"]
            )
            code = (
                0
                if report.execution.run_status == "completed"
                else 130
                if report.execution.run_status == "interrupted"
                else 1
            )
        elif args.command == "inspect":
            result = inspect(args.output_dir)
        else:
            result = replay(args.ledger, args.prices, args.output_dir)["summary"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        files.subprocess.SubprocessError,
    ):
        print(
            json.dumps(
                dict(
                    status="failed",
                    error="usage_input_io_or_execution_invalid",
                    notice="Keep existing evidence; use a new directory.",
                )
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
