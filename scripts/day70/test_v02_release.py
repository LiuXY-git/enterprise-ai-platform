"""Regression checks for release drift, status transitions and false success."""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_gate as gate  # noqa: E402
import verify_v02 as verifier  # noqa: E402


@pytest.fixture
def release_copy(tmp_path):
    manifest = json.loads((gate.ROOT / gate.MANIFEST).read_text(encoding="utf-8"))
    old = json.loads(
        (gate.ROOT / "agent-center/release-v0.1.0.json").read_text(encoding="utf-8")
    )
    names = {a["path"] for a in manifest["artifacts"] + old["artifacts"]}
    for name in names:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(gate.ROOT / name, target)
    return tmp_path, copy.deepcopy(manifest)


def test_real_release_and_old_inventory():
    result = gate.validate()
    assert result["unique_historical_tests"] == 648
    assert result["tests_executed_by_this_check"] == 0
    assert result["v01_integrity"]["frozen_artifacts"] == 70
    assert not result["remote_tag_or_release_checked"]


@pytest.mark.parametrize(
    "status,released", [("candidate", None), ("released", "2026-09-24")]
)
def test_candidate_and_finalized_content_both_pass(release_copy, status, released):
    root, manifest = release_copy
    manifest.update(release_status=status, release_date=released)
    assert gate.validate(root, manifest)["release_status"] == status


@pytest.mark.parametrize(
    "status,released",
    [
        ("candidate", "2026-09-24"),
        ("released", None),
        ("released", "bad"),
        ("published", None),
    ],
)
def test_invalid_status_date(release_copy, status, released):
    root, manifest = release_copy
    manifest.update(release_status=status, release_date=released)
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name",
    ["experiments/day68/tool_registry.py", "docs/evidence/day69/live-no_sales.json"],
)
def test_changed_asset_rejected(release_copy, name):
    root, manifest = release_copy
    (root / name).write_text("changed", encoding="utf-8")
    with pytest.raises(gate.ReleaseError, match="artifact_hash_mismatch"):
        gate.validate(root, manifest)


def test_crlf_is_portable(release_copy):
    root, manifest = release_copy
    path = root / "experiments/day69/briefing.py"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert gate.validate(root, manifest)["status"] == "passed"


@pytest.mark.parametrize("action", ["omit", "duplicate", "extra", "missing"])
def test_inventory_cannot_be_silently_reduced_or_expanded(release_copy, action):
    root, manifest = release_copy
    if action == "omit":
        manifest["artifacts"].pop()
    elif action == "duplicate":
        manifest["artifacts"].append(manifest["artifacts"][0])
    elif action == "extra":
        (root / "experiments/day69/unreviewed.py").write_text("pass", encoding="utf-8")
    else:
        (root / manifest["artifacts"][0]["path"]).unlink()
    with pytest.raises(gate.ReleaseError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "C:/secrets",
        ".env",
        "experiments\\day69\\briefing.py",
        "experiments/day69/../day69/briefing.py",
    ],
)
def test_outside_paths_rejected(release_copy, name):
    root, manifest = release_copy
    manifest["artifacts"][0]["path"] = name
    with pytest.raises(gate.ReleaseError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "2.0.0"),
        ("capabilities", {"mcp": "verified"}),
        ("unique_test_counts", {"day69": 999}),
        ("hash_normalization", "none"),
    ],
)
def test_unsupported_claims_rejected(release_copy, field, value):
    root, manifest = release_copy
    manifest[field] = value
    with pytest.raises(gate.ReleaseError, match="manifest_claim_mismatch"):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name", ["experiments/day69/briefing.py", "docs/evidence/day69/live-no_sales.json"]
)
def test_refreezing_changed_file_does_not_bypass_history(release_copy, name):
    root, manifest = release_copy
    (root / name).write_text("changed", encoding="utf-8")
    next(a for a in manifest["artifacts"] if a["path"] == name)["sha256"] = gate.digest(
        root / name
    )
    with pytest.raises(gate.ReleaseError, match="historical_hash_mismatch"):
        gate.validate(root, manifest)


def test_v01_drift_is_still_detected(release_copy):
    root, manifest = release_copy
    (root / "experiments/day62/system-prompt.md").write_text(
        "changed", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "xml",
    [
        "<testsuites/>",
        '<testsuite tests="1" failures="0" errors="0" skipped="0"/>',
        '<testsuite tests="1"><testcase/></testsuite>',
        '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase><skipped/></testcase></testsuite>',
    ],
)
def test_bad_junit_cannot_claim_pass(tmp_path, xml):
    path = tmp_path / "test.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        verifier.junit_counts(path)


def test_valid_junit(tmp_path):
    path = tmp_path / "test.xml"
    path.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase/></testsuite></testsuites>',
        encoding="utf-8",
    )
    verifier.require_passed(verifier.junit_counts(path), 1)


@pytest.mark.parametrize(
    "field,value", [("tests", 647), ("failures", 1), ("errors", 1), ("skipped", 1)]
)
def test_not_all_passed(field, value):
    counts = {"tests": 648, "failures": 0, "errors": 0, "skipped": 0}
    counts[field] = value
    with pytest.raises(ValueError):
        verifier.require_passed(counts, 648)


def test_runner_refuses_existing_output(tmp_path):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        verifier.verify(tmp_path, Path(sys.executable))
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("failure", ["exit", "timeout", "skip", "drift"])
def test_runner_preserves_failure_and_never_writes_success(
    tmp_path, monkeypatch, failure
):
    root = tmp_path / "repo"
    manifest = root / gate.MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr(verifier, "validate", lambda root: {"status": "passed"})
    monkeypatch.setattr(verifier, "SUITES", [("small", 1, ["test.py"])])

    def fake_run(*args, **kwargs):
        assert "--live" not in args[0]
        if failure == "timeout":
            raise subprocess.TimeoutExpired("pytest", 300, output=b"partial log")
        skipped = int(failure == "skip")
        xml = f'<testsuite tests="1" failures="0" errors="0" skipped="{skipped}"><testcase>{"<skipped/>" if skipped else ""}</testcase></testsuite>'
        (output / "small.xml").write_text(xml, encoding="utf-8")
        if failure == "drift":
            manifest.write_text('{"changed":true}', encoding="utf-8")
        return SimpleNamespace(
            returncode=int(failure == "exit"), stdout="saved log", stderr=""
        )

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    with pytest.raises(ValueError):
        verifier.verify(output, Path(sys.executable), root)
    assert (output / "small.txt").exists()
    assert json.loads((output / "failure.json").read_text())["status"] == "failed"
    assert not (output / "verification.json").exists()
