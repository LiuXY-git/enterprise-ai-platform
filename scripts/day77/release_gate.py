"""Offline v0.5 candidate/released inventory and historical evidence checks."""

import hashlib
import importlib.util
import json
import re
from datetime import date
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = "agent-center/release-v0.5.0.json"
DIRECTORIES = (
    *[f"experiments/day{d}" for d in (72, 73, 75, 76)],
    *[f"docs/evidence/day{d}" for d in range(72, 77)],
    "scripts/day77",
    "agent-center/v0.5",
)
FIXED = (
    "agent-center/release-v0.2.0.json",
    "scripts/day70/release_gate.py",
    "scripts/day70/verify_v02.py",
    "docs/day71-mcp-basics.md",
    "docs/day72-mcp-server.md",
    "docs/day73-agent-mcp.md",
    "docs/day74-agent-memory.md",
    "docs/day75-conversation-memory-plan.md",
    "docs/day75-conversation-memory.md",
    "docs/day76-planning.md",
    "docs/day77-agent-v05-release.md",
    "docs/agent-center-v0.5.md",
    "docs/week-11-summary.md",
)
IGNORED = {".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
COUNTS = {
    "day59": 49,
    "day64": 141,
    "day65_sql": 67,
    "day72": 32,
    "day73": 79,
    "day75": 50,
}
CAPABILITIES = {
    "mcp_server": "local_stdio_fictional_readonly_sales",
    "agent_mcp": "four_fixed_cases_two_live_qwen_cases_historically_verified",
    "conversation_memory": "separate_cli_sqlite_thread_scoped_fixed_department_intents",
    "memory_restore": "separate_process_verified_with_update_clear_and_request_replay",
    "planning": "existing_day59_plan_only_and_day76_human_authored_examples",
    "memory_mcp_planning_integration": "not_implemented",
    "cross_thread_long_term_memory": "not_implemented",
    "arbitrary_task_execution": "not_implemented",
    "production_authentication": "not_implemented",
    "agent_http_api": "not_implemented",
    "release_kind": "independent_learning_experiment_collection",
}
EVIDENCE = {f"day{d}": f"docs/evidence/day{d}/validation.json" for d in range(72, 77)}
MUTABLE_HISTORY = {"README.md", "docs/README.md", "docs/week-11-plan.md", ".gitignore"}
HISTORY_EXCEPTIONS = {"day74": ["docs/day75-conversation-memory-plan.md"]}


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


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def template():
    return {
        "product": "Agent Center",
        "version": "0.5.0",
        "component_tag": "agent-center-v0.5.0",
        "platform_api_version": "1.0.0",
        "release_status": "candidate",
        "release_date": None,
        "hash_algorithm": "sha256",
        "hash_normalization": "CRLF_to_LF",
        "capabilities": CAPABILITIES,
        "unique_regression_test_counts": COUNTS,
        "evidence": EVIDENCE,
        "mutable_history_paths": sorted(MUTABLE_HISTORY),
        "historical_document_exceptions": HISTORY_EXCEPTIONS,
    }


def validate(root=ROOT, manifest=None):
    root = Path(root).resolve()
    if manifest is None:
        manifest = json.loads(safe_path(root, MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ReleaseError("invalid_manifest")
    for key, value in template().items():
        if key not in ("release_status", "release_date") and manifest.get(key) != value:
            raise ReleaseError("manifest_claim_mismatch:" + key)
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
    expected_names = set(inventory(root))
    assets = manifest.get("artifacts")
    if not isinstance(assets, list) or not assets:
        raise ReleaseError("invalid_artifacts")
    names = []
    for item in assets:
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
    # The parent gate is executable code; verify its v0.5 hash before importing it.
    parent_gate = load_module(root / "scripts/day70/release_gate.py", "v05_parent_gate")
    parent = parent_gate.validate(root)
    allowed = set(names)
    for parent_manifest in (
        "agent-center/release-v0.1.0.json",
        "agent-center/release-v0.2.0.json",
    ):
        record = json.loads(
            safe_path(root, parent_manifest).read_text(encoding="utf-8")
        )
        allowed.update(a["path"] for a in record["artifacts"])
    linked = {"source_hashes": 0, "evidence_hashes": 0, "excluded_document_hashes": 0}
    for day, location in EVIDENCE.items():
        record = json.loads(safe_path(root, location).read_text(encoding="utf-8"))
        source = record.get("source_hashes", record.get("document_hashes"))
        if not isinstance(source, dict) or not source:
            raise ReleaseError("missing_historical_hashes")
        for name, expected in source.items():
            if name in MUTABLE_HISTORY or name in HISTORY_EXCEPTIONS.get(day, []):
                linked["excluded_document_hashes"] += 1
                continue
            if name not in allowed or digest(safe_path(root, name)) != expected:
                raise ReleaseError("historical_hash_mismatch:" + name)
            linked["source_hashes"] += 1
        evidence = record.get("evidence_hashes", {})
        if not isinstance(evidence, dict) or (day != "day74" and not evidence):
            raise ReleaseError("missing_evidence_hashes")
        for name, expected in evidence.items():
            full_name = (PurePosixPath(location).parent / name).as_posix()
            if full_name not in names or digest(safe_path(root, full_name)) != expected:
                raise ReleaseError("historical_evidence_mismatch")
            linked["evidence_hashes"] += 1
    return {
        "status": "passed",
        "version": "0.5.0",
        "release_status": status,
        "frozen_artifacts": len(names),
        "historical_hashes_checked": linked,
        "unique_regression_tests_required": sum(COUNTS.values()),
        "v02_and_v01_integrity": parent,
        "tests_executed_by_this_check": 0,
        "new_model_requests": 0,
        "remote_tag_or_release_checked": False,
    }


def main():
    try:
        print(json.dumps(validate(), indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
