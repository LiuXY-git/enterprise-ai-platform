"""Offline inventory, historical links and explicit deferred-video checks."""

import hashlib
import importlib.util
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "agent-center/release-v1.0.0.json"
DIRECTORIES = (
    *[f"experiments/day{day}" for day in range(78, 83)],
    *[f"docs/evidence/day{day}" for day in range(78, 83)],
    "scripts/day84",
    "agent-center/v1.0",
    "demo/day83",
)
FIXED = (
    "agent-center/release-v0.5.0.json",
    "scripts/day77/release_gate.py",
    "scripts/day77/verify_v05.py",
    "docs/day78-task-logging.md",
    "docs/day79-error-recovery.md",
    "docs/day80-human-in-the-loop.md",
    "docs/day81-complex-business-tests.md",
    "docs/day82-prompt-optimization.md",
    "docs/day83-agent-demo.md",
    "docs/day84-agent-v1-release.md",
    "docs/agent-center-v1.0.md",
    "docs/week-12-summary.md",
)
IGNORED = {".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
COUNTS = {
    "day59": 49,
    "day64": 141,
    "day65_sql": 67,
    "day72": 32,
    "day73": 79,
    "day75": 50,
    "day78": 39,
    "day79": 66,
    "day80": 55,
    "day81": 39,
    "day82": 60,
}
CAPABILITIES = {
    "release_kind": "host_cli_learning_collection_with_fixed_sales_workflow",
    "task_logs": "sqlite_safe_event_replay_not_execution_resume",
    "recovery": "bounded_transient_retries_and_validated_receipt_fallback",
    "human_approval": "local_content_bound_expiring_approval_with_atomic_simulated_outbox",
    "business_acceptance": "15_fixed_sales_scenarios",
    "prompt": "candidate_in_separate_entrypoint_with_paired_replay_and_optional_live_evaluation",
    "prompt_quality_improvement": "not_measured",
    "memory_planning_mcp_integration": "not_implemented",
    "arbitrary_task_execution": "not_implemented",
    "agent_http_api": "not_implemented",
    "production_authentication": "not_implemented",
    "external_delivery": "not_implemented_in_this_workflow",
}
DEFERRED = {
    "status": "deferred",
    "requested_on": "2026-09-28",
    "reason": "user_cannot_record_now_continue_release_preparation",
    "recording_file": None,
    "recording_verified": False,
    "checklist": "demo/day83/recording-status.json",
}


class ReleaseError(ValueError):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def safe_path(root, name):
    if not isinstance(name, str) or not name:
        raise ReleaseError("invalid_asset_path")
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in name
        or ":" in name
        or relative.as_posix() != name
    ):
        raise ReleaseError("invalid_asset_path")
    root = root.resolve()
    path = root / name
    if not path.resolve().is_relative_to(root) or any(
        p.is_symlink() for p in [path, *path.parents] if p != root
    ):
        raise ReleaseError("asset_escapes_repository")
    if not path.is_file():
        raise ReleaseError("missing_asset")
    return path


def inventory(root):
    names = set(FIXED)
    for folder in DIRECTORIES:
        directory = root / folder
        if not directory.is_dir():
            raise ReleaseError("missing_directory")
        for path in directory.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and not IGNORED.intersection(relative.parts):
                names.add(relative.as_posix())
    for name in names:
        safe_path(root, name)
    return sorted(names)


def template():
    return {
        "product": "Agent Center",
        "version": "1.0.0",
        "component_tag": "agent-center-v1.0.0",
        "platform_api_version": "1.0.0",
        "release_status": "candidate",
        "release_date": None,
        "hash_algorithm": "sha256",
        "hash_normalization": "CRLF_to_LF",
        "capabilities": CAPABILITIES,
        "unique_regression_test_counts": COUNTS,
        "demo_video": DEFERRED,
        "historical_evidence": {
            f"day{d}": f"docs/evidence/day{d}/validation.json" for d in range(78, 83)
        },
        "candidate_evidence_exclusion": "docs/evidence/day84 is output and is not included in its own manifest",
    }


def validate(root=ROOT, manifest=None):
    root = Path(root).resolve()
    if manifest is None:
        manifest = json.loads(safe_path(root, MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != set(template()) | {
        "artifacts"
    }:
        raise ReleaseError("invalid_manifest")
    for key, expected in template().items():
        if key not in {"release_status", "release_date"} and manifest[key] != expected:
            raise ReleaseError("manifest_claim_mismatch:" + key)
    status, released = manifest["release_status"], manifest["release_date"]
    if status == "candidate":
        if released is not None:
            raise ReleaseError("candidate_has_release_date")
    elif status == "released":
        if (
            not isinstance(released, str)
            or date.fromisoformat(released).isoformat() != released
        ):
            raise ReleaseError("invalid_release_date")
    else:
        raise ReleaseError("invalid_release_status")
    expected_names = set(inventory(root))
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise ReleaseError("invalid_artifacts")
    names = []
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ReleaseError("invalid_artifact_record")
        name, expected = item["path"], item["sha256"]
        path = safe_path(root, name)
        if name not in expected_names:
            raise ReleaseError("asset_outside_scope")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ReleaseError("invalid_digest")
        if digest(path) != expected:
            raise ReleaseError("artifact_hash_mismatch:" + name)
        names.append(name)
    if len(names) != len({n.casefold() for n in names}) or set(names) != expected_names:
        raise ReleaseError("artifact_inventory_mismatch")
    # Import parent gate only after checking its recorded digest.
    spec = importlib.util.spec_from_file_location(
        "v10_parent", root / "scripts/day77/release_gate.py"
    )
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    previous = parent.validate(root)
    linked = 0
    for day, location in manifest["historical_evidence"].items():
        record = json.loads(safe_path(root, location).read_text(encoding="utf-8"))
        source = record.get("source_sha256_lf")
        if (
            record.get("status") != "passed"
            or record.get("day") != int(day[3:])
            or not isinstance(source, dict)
            or not source
        ):
            raise ReleaseError("invalid_historical_evidence")
        for name, expected in source.items():
            if name not in names or digest(safe_path(root, name)) != expected:
                raise ReleaseError("historical_hash_mismatch:" + name)
            linked += 1
    video = json.loads(
        safe_path(root, DEFERRED["checklist"]).read_text(encoding="utf-8")
    )
    if video != DEFERRED:
        raise ReleaseError("demo_status_mismatch")
    return {
        "status": "passed",
        "version": "1.0.0",
        "release_status": status,
        "frozen_artifacts": len(names),
        "historical_source_hashes_checked": linked,
        "unique_regression_tests_required": sum(COUNTS.values()),
        "demo_video_status": "deferred",
        "prompt_quality_improvement": "not_measured",
        "v05_integrity": previous,
        "tests_executed_by_this_check": 0,
        "new_model_requests": 0,
        "remote_tag_or_release_checked": False,
    }


def main():
    try:
        print(json.dumps(validate(), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
