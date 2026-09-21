"""Read-only integrity gate for the Agent Center v0.1 release inventory."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "agent-center/release-v0.1.0.json"
FROZEN_DIRS = (
    *[f"experiments/day{day}" for day in range(58, 63)],
    *[f"docs/evidence/day{day}" for day in range(58, 63)],
    "demo/agent-center",
    "scripts/day63",
)
FIXED_FILES = (
    "backend/app/settings.py",
    "requirements.txt",
    "requirements-dev.txt",
    "docs/day57-agent-architecture.md",
    "docs/day58-langgraph-basics.md",
    "docs/day59-task-planner.md",
    "docs/day60-task-state.md",
    "docs/day61-sales-agent-scenario.md",
    "docs/day62-agent-prompt.md",
    "docs/day63-agent-center-release.md",
    "docs/agent-center-v0.1.md",
    "docs/week-9-summary.md",
    "agent-center/README.md",
)
IGNORED_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
CAPABILITIES = {
    "langgraph_mock_flow": "verified",
    "model_task_planning": "qwen_verified_on_fictional_tasks",
    "sqlite_simulated_progress_recovery": "verified",
    "sales_scenario_contract": "offline_verified",
    "sales_report_prompt": "qwen_verified_on_fictional_snapshots",
    "live_business_tools": "not_implemented",
    "agent_http_api": "not_implemented",
    "sales_report_checkpoint_integration": "not_implemented",
    "cross_thread_memory": "not_implemented",
}
EVIDENCE = {
    "day58": "docs/evidence/day58/graph-validation.json",
    **{f"day{day}": f"docs/evidence/day{day}/validation.json" for day in range(59, 63)},
}
TEST_COUNTS = {"day58": 14, "day59": 49, "day60": 23, "day61": 57, "day62": 59}


class ReleaseError(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def safe_asset(root: Path, name: str) -> Path:
    if not isinstance(name, str):
        raise ReleaseError("invalid_asset_path")
    posix = PurePosixPath(name)
    if (
        "\\" in name
        or posix.is_absolute()
        or ".." in posix.parts
        or posix.as_posix() != name
        or ":" in name
    ):
        raise ReleaseError("invalid_asset_path")
    if name not in FIXED_FILES and not any(
        name.startswith(folder + "/") for folder in FROZEN_DIRS
    ):
        raise ReleaseError("asset_outside_release_scope")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ReleaseError("asset_escapes_repository")
    if not target.is_file():
        raise ReleaseError("missing_asset")
    return target


def inventory(root: Path) -> list[str]:
    names = set(FIXED_FILES)
    for directory in FROZEN_DIRS:
        for path in (root / directory).rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and not IGNORED_DIRS.intersection(relative.parts):
                names.add(relative.as_posix())
    for name in names:
        safe_asset(root, name)
    return sorted(names)


def validate(root: Path = ROOT, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReleaseError("invalid_manifest")
    if (
        manifest.get("product") != "Agent Center"
        or manifest.get("version") != "0.1.0"
        or manifest.get("component_tag") != "agent-center-v0.1.0"
        or manifest.get("platform_api_version") != "1.0.0"
    ):
        raise ReleaseError("invalid_component_identity")
    status = manifest.get("release_status")
    released = manifest.get("release_date")
    if status == "candidate":
        if released is not None:
            raise ReleaseError("candidate_cannot_have_release_date")
    elif status == "released":
        try:
            if (
                not isinstance(released, str)
                or date.fromisoformat(released).isoformat() != released
            ):
                raise ValueError
        except ValueError:
            raise ReleaseError("released_requires_valid_date") from None
    else:
        raise ReleaseError("invalid_release_status")
    if manifest.get("capabilities") != CAPABILITIES:
        raise ReleaseError("unsupported_capability_claim")
    if (
        manifest.get("evidence") != EVIDENCE
        or manifest.get("unique_test_counts") != TEST_COUNTS
    ):
        raise ReleaseError("evidence_or_test_inventory_mismatch")
    if (
        manifest.get("hash_normalization") != "CRLF_to_LF"
        or manifest.get("hash_algorithm") != "sha256"
    ):
        raise ReleaseError("unsupported_hash_format")
    assets = manifest.get("artifacts")
    if not isinstance(assets, list) or not assets:
        raise ReleaseError("invalid_artifact_inventory")
    names = []
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {"path", "sha256"}:
            raise ReleaseError("invalid_artifact_record")
        name = asset["path"]
        path = safe_asset(root, name)
        names.append(name)
        if not isinstance(asset["sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", asset["sha256"]
        ):
            raise ReleaseError("invalid_digest")
        if digest(path) != asset["sha256"]:
            raise ReleaseError("artifact_hash_mismatch")
    if len(names) != len({name.casefold() for name in names}):
        raise ReleaseError("duplicate_artifact")
    if sorted(names) != inventory(root):
        raise ReleaseError("artifact_inventory_mismatch")
    linked_hashes = 0
    for path in EVIDENCE.values():
        evidence = json.loads(safe_asset(root, path).read_text(encoding="utf-8"))
        for name, expected in evidence.get("source_hashes", {}).items():
            if name not in names or digest(safe_asset(root, name)) != expected:
                raise ReleaseError("historical_source_hash_mismatch")
            linked_hashes += 1
    return {
        "status": "passed",
        "product": "Agent Center",
        "version": "0.1.0",
        "release_status": status,
        "frozen_artifacts": len(names),
        "historical_source_hashes_checked": linked_hashes,
        "unique_historical_tests": sum(TEST_COUNTS.values()),
        "tests_executed_by_this_check": 0,
        "new_model_requests": 0,
        "remote_tag_or_release_checked": False,
    }


def main() -> int:
    try:
        result = validate()
    except (ReleaseError, OSError, ValueError, TypeError, KeyError):
        print(
            json.dumps({"status": "failed", "error": "release_integrity_check_failed"})
        )
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
