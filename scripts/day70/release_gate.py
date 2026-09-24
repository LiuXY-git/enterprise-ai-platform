"""Check the v0.2 inventory and historical evidence without network or pytest."""

import hashlib
import importlib.util
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "agent-center/release-v0.2.0.json"
DIRECTORIES = (
    *[f"experiments/day{day}" for day in range(64, 70)],
    *[f"docs/evidence/day{day}" for day in range(64, 70)],
    "scripts/day70",
    "agent-center/v0.2",
)
FIXED = (
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "backend/app/settings.py",
    "backend/app/services/retrieval_service.py",
    "backend/app/services/embedding_service.py",
    "backend/app/services/vector_store.py",
    "tests/conftest.py",
    "tests/test_retrieval_service.py",
    "scripts/day63/check_release.py",
    "agent-center/release-v0.1.0.json",
    "docs/day64-function-calling.md",
    "docs/day65-sql-tool.md",
    "docs/day66-knowledge-tool.md",
    "docs/day67-api-tool.md",
    "docs/day68-multi-tool.md",
    "docs/day69-complex-task-tests.md",
    "docs/day70-agent-v02-release.md",
    "docs/agent-center-v0.2.md",
    "docs/week-10-summary.md",
)
IGNORED = {".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
COUNTS = {
    "day64": 141,
    "day65": 96,
    "day66": 120,
    "day67": 123,
    "day68": 83,
    "day69": 84,
    "existing_retrieval": 1,
}
EVIDENCE = {f"day{d}": f"docs/evidence/day{d}/validation.json" for d in range(64, 70)}
CAPABILITIES = {
    "function_calling": "qwen_verified_fictional_examples",
    "sql_tool": "fixed_read_only_select_fictional_database",
    "knowledge_tool": "existing_hub_isolated_fictional_collection_verified",
    "weather_tool": "fixed_open_meteo_endpoint_verified",
    "multi_tool_orchestration": "bounded_single_sales_visit_task",
    "receipt_briefing": "deterministic_with_sources_and_missing_items",
    "failure_recovery": "manual_new_session_rerun_only",
    "agent_http_api": "not_implemented",
    "tool_chain_checkpoint_resume": "not_implemented",
    "arbitrary_goal_planning": "not_implemented",
    "business_writes_and_notifications": "not_implemented",
    "mcp_and_cross_thread_memory": "not_implemented",
    "business_truth_and_general_model_semantics": "not_verified",
}


class ReleaseError(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def safe_asset(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name:
        raise ReleaseError("invalid_asset_path")
    posix = PurePosixPath(name)
    if (
        posix.is_absolute()
        or ".." in posix.parts
        or "\\" in name
        or ":" in name
        or posix.as_posix() != name
    ):
        raise ReleaseError("invalid_asset_path")
    if name not in FIXED and not any(name.startswith(d + "/") for d in DIRECTORIES):
        raise ReleaseError("asset_outside_scope")
    root = root.resolve()
    path = root / name
    if not path.resolve().is_relative_to(root):
        raise ReleaseError("asset_escapes_repository")
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root):
        raise ReleaseError("symlink_asset")
    if not path.is_file():
        raise ReleaseError("missing_asset")
    return path


def inventory(root: Path) -> list[str]:
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
        safe_asset(root, name)
    return sorted(names)


def validate(root: Path = ROOT, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReleaseError("invalid_manifest")
    for field, expected in {
        "product": "Agent Center",
        "version": "0.2.0",
        "component_tag": "agent-center-v0.2.0",
        "platform_api_version": "1.0.0",
        "hash_algorithm": "sha256",
        "hash_normalization": "CRLF_to_LF",
        "capabilities": CAPABILITIES,
        "unique_test_counts": COUNTS,
        "evidence": EVIDENCE,
    }.items():
        if manifest.get(field) != expected:
            raise ReleaseError("manifest_claim_mismatch:" + field)
    status, released = manifest.get("release_status"), manifest.get("release_date")
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
    assets = manifest.get("artifacts")
    if not isinstance(assets, list) or not assets:
        raise ReleaseError("invalid_artifacts")
    names = []
    for item in assets:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ReleaseError("invalid_artifact_record")
        name, expected = item["path"], item["sha256"]
        path = safe_asset(root, name)
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ReleaseError("invalid_digest")
        if digest(path) != expected:
            raise ReleaseError("artifact_hash_mismatch:" + name)
        names.append(name)
    if len(names) != len({n.casefold() for n in names}):
        raise ReleaseError("duplicate_artifact")
    if sorted(names) != inventory(root):
        raise ReleaseError("artifact_inventory_mismatch")
    linked = {"source_hashes": 0, "evidence_hashes": 0}
    for validation_path in EVIDENCE.values():
        record = json.loads(
            safe_asset(root, validation_path).read_text(encoding="utf-8")
        )
        for key in linked:
            hashes = record.get(key)
            if not isinstance(hashes, dict) or not hashes:
                raise ReleaseError("missing_historical_hashes")
            for name, expected in hashes.items():
                if key == "evidence_hashes":
                    name = (PurePosixPath(validation_path).parent / name).as_posix()
                if name not in names or digest(safe_asset(root, name)) != expected:
                    raise ReleaseError("historical_hash_mismatch")
                linked[key] += 1
    # Run the original v0.1 gate only after checking its source and manifest hashes.
    spec = importlib.util.spec_from_file_location(
        "agent_v01_gate", root / "scripts/day63/check_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = module.validate(root)
    return {
        "status": "passed",
        "version": "0.2.0",
        "release_status": status,
        "frozen_artifacts": len(names),
        "historical_hashes_checked": linked,
        "unique_historical_tests": sum(COUNTS.values()),
        "v01_integrity": old,
        "tests_executed_by_this_check": 0,
        "new_model_requests": 0,
        "remote_tag_or_release_checked": False,
    }


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
