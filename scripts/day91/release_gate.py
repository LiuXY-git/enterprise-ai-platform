"""Evaluation Center v0.1 inventory and historical evidence, without executing Agent."""

import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day85.contracts import canonical_hash  # noqa: E402
from experiments.day86.dataset_tool import load_dataset, read_json  # noqa: E402
from scripts.day84.v10_gate import IGNORED, digest, safe_path  # noqa: E402

MANIFEST = "evaluation-center/release-v0.1.0.json"
HISTORY = (85, 87, 88, 89, 90)  # Day 86 acceptance was delivered together with Day 87.
DIRECTORIES = tuple(
    [f"experiments/day{d}" for d in range(85, 91)]
    + [f"docs/evidence/day{d}" for d in range(85, 91)]
    + ["evaluation-center/datasets", "evaluation-center/v0.1", "scripts/day91"]
)
FIXED = (
    "experiments/day73/requirements-lock.txt",
    "experiments/day73/requirements.txt",
    "experiments/day72/requirements.txt",
    "evaluation-center/design.md",
    "agent-center/release-v1.0.0.json",
    "scripts/day84/v10_gate.py",
    "scripts/day84/verify_v10.py",
    "scripts/day84/test_v10_release.py",
    "experiments/day64/test_chat_tools.py",
    "docs/day85-evaluation-framework.md",
    "docs/day86-test-dataset.md",
    "docs/day87-evaluation-runner.md",
    "docs/day88-latency.md",
    "docs/day89-token-cost.md",
    "docs/day90-success-rate.md",
    "docs/day91-evaluation-release.md",
    "docs/evaluation-center-v0.1.md",
    "docs/week-13-summary.md",
)
COUNTS = dict(
    transport=56,
    framework=59,
    dataset=32,
    execution=35,
    latency=28,
    usage=34,
    scoring=54,
    agent_release_protection=44,
)
RELEASE_TESTS = 41
CAPABILITIES = dict(
    adapter="fixed_day82_fixture_real_local_stdio_mcp",
    dataset="12_versioned_fictional_sales_cases_smoke_is_4_case_subset",
    scoring="independent_deterministic_rules_and_exact_answer_template",
    success_rate="passed_over_all_selected_errors_retained_incomplete_null",
    latency="parent_case_monotonic_elapsed_including_startup_retries_cleanup",
    usage="offline_tested_usage_observer_fixture_tokens_unknown",
    cost="explicit_flat_text_decimal_estimate_not_provider_invoice",
    live_model_evaluation="not_integrated",
    arbitrary_agent_adapter="not_implemented",
    web_dashboard="not_implemented",
    production_quality_claim="not_measured",
)
EXCLUDED = {
    "day85:evaluation-center/README.md": "816442e5b112a983391d87c5168130801c746e45ca935769d483f9c6eb1cbae1"
}


def historical(root):
    return {
        day: read_json(safe_path(root, f"docs/evidence/day{day}/validation.json"))
        for day in HISTORY
    }


def inventory(root):
    names = set(FIXED)
    for folder in DIRECTORIES:
        directory = root / folder
        if not directory.is_dir():
            raise ValueError("missing_release_directory")
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and not IGNORED.intersection(relative.parts):
                names.add(relative.as_posix())
    for day, record in historical(root).items():
        names.update(
            n for n in record["source_sha256_lf"] if f"day{day}:{n}" not in EXCLUDED
        )
    # Runtime provenance includes the frozen local MCP adapter dependencies.
    score = read_json(safe_path(root, "docs/evidence/day90/scoring.json"))
    names.update(score["source"]["execution"]["source_sha256_lf"])
    for name in names:
        safe_path(root, name)
    return sorted(names)


def template():
    return dict(
        schema_version="evaluation-release-v1",
        product="Evaluation Center",
        version="0.1.0",
        component_tag="evaluation-center-v0.1.0",
        platform_api_version="1.0.0",
        release_status="candidate",
        release_date=None,
        hash_algorithm="sha256",
        hash_normalization="CRLF_to_LF",
        capabilities=CAPABILITIES,
        unique_regression_test_counts=COUNTS,
        release_tests_required=RELEASE_TESTS,
        historical_evidence={
            f"day{d}": f"docs/evidence/day{d}/validation.json" for d in HISTORY
        },
        excluded_historical_navigation_hashes=EXCLUDED,
        output_exclusion="docs/evidence/day91 and data/day91 are verification outputs, not self-hashed release inputs",
        deferred=dict(
            day83_video="deferred",
            day82_live_prompt_improvement="not_measured",
            live_evaluation="not_integrated",
        ),
    )


def build(root=ROOT):
    return {
        **template(),
        "artifacts": [
            dict(path=n, sha256=digest(safe_path(root, n))) for n in inventory(root)
        ],
    }


def validate(root=ROOT, manifest=None):
    root = Path(root).resolve()
    manifest = read_json(safe_path(root, MANIFEST)) if manifest is None else manifest
    expected = template()
    if not isinstance(manifest, dict) or set(manifest) != set(expected) | {"artifacts"}:
        raise ValueError("invalid_manifest")
    for key, value in expected.items():
        if key not in {"release_status", "release_date"} and canonical_hash(
            manifest[key]
        ) != canonical_hash(value):
            raise ValueError("manifest_claim_mismatch:" + key)
    status, released = manifest["release_status"], manifest["release_date"]
    if status == "candidate":
        if released is not None:
            raise ValueError("candidate_has_date")
    elif status == "released":
        if (
            not isinstance(released, str)
            or date.fromisoformat(released).isoformat() != released
        ):
            raise ValueError("release_date_invalid")
    else:
        raise ValueError("release_status_invalid")
    names = inventory(root)
    entries = manifest["artifacts"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("invalid_artifact_list")
    actual = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ValueError("invalid_artifact_entry")
        path = safe_path(root, entry["path"])
        if not isinstance(entry["sha256"], str) or not re.fullmatch(
            "[a-f0-9]{64}", entry["sha256"]
        ):
            raise ValueError("invalid_digest")
        if digest(path) != entry["sha256"]:
            raise ValueError("artifact_hash_mismatch:" + entry["path"])
        actual.append(entry["path"])
    if len(actual) != len(set(n.casefold() for n in actual)) or set(actual) != set(
        names
    ):
        raise ValueError("artifact_inventory_mismatch")
    sources = evidence_links = 0
    excluded = {}
    for day, record in historical(root).items():
        if (
            record["day"] != day
            or record["status"] != "passed"
            or record["model_requests"] != 0
        ):
            raise ValueError("historical_status_invalid")
        for name, value in record["source_sha256_lf"].items():
            key = f"day{day}:{name}"
            if key in EXCLUDED:
                excluded[key] = value
            else:
                if name not in names or digest(safe_path(root, name)) != value:
                    raise ValueError("historical_source_mismatch")
                sources += 1
        for name, value in record.get(
            "evidence_sha256_lf", record.get("evidence_hashes", {})
        ).items():
            path = f"docs/evidence/day{day}/{name}"
            if path not in names or digest(safe_path(root, path)) != value:
                raise ValueError("historical_evidence_mismatch")
            evidence_links += 1
    if excluded != EXCLUDED:
        raise ValueError("excluded_history_changed")
    spec = importlib.util.spec_from_file_location(
        "evaluation_parent_gate", root / "scripts/day84/v10_gate.py"
    )
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    previous = parent.validate(root)
    dataset = load_dataset(
        root / "evaluation-center/datasets/sales-prepare-v1.0.0.json", root
    )
    from experiments.day90.scoring import ScoredReport, judge

    score = ScoredReport.model_validate(
        read_json(root / "docs/evidence/day90/scoring.json")
    )
    if score.summary["passed"] != 12 or not score.full_dataset_evaluated:
        raise ValueError("historical_full_score_missing")
    if canonical_hash(
        score.source.execution.plan.dataset.model_dump()
    ) != canonical_hash(dataset.model_dump()):
        raise ValueError("historical_dataset_mismatch")
    cases = {c.case_id: c for c in dataset.cases}
    for row, grade in zip(score.source.execution.rows, score.results, strict=True):
        directory = root / "docs/evidence/day90/cases" / row.case_id
        recalculated = judge(
            cases[row.case_id],
            row.observed,
            read_json(directory / "generation.json"),
            read_json(directory / "events.json"),
        )
        if canonical_hash(recalculated.model_dump()) != canonical_hash(
            grade.model_dump()
        ):
            raise ValueError("historical_grade_mismatch")
    return dict(
        status="passed",
        product="Evaluation Center",
        version="0.1.0",
        release_status=status,
        frozen_artifacts=len(names),
        historical_source_links=sources,
        historical_evidence_links=evidence_links,
        excluded_navigation_links=len(excluded),
        unique_regression_tests_required=sum(COUNTS.values()),
        release_tests_required=RELEASE_TESTS,
        historical_fixture_score=score.summary,
        parent_agent_integrity=previous,
        tests_executed_by_this_check=0,
        new_model_requests=0,
        remote_tag_or_release_checked=False,
    )


if __name__ == "__main__":
    try:
        print(json.dumps(validate(), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps(dict(status="failed", error="release_integrity_invalid")))
        raise SystemExit(1) from None
