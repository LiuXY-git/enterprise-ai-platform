"""Release gates must detect drift and never count skipped tests as passed."""

import copy
import json
import shutil

import pytest
from check_release import MANIFEST, ROOT, ReleaseError, digest, validate
from verify_release import junit_counts, require_passed


@pytest.fixture
def release_copy(tmp_path):
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        destination = tmp_path / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / item["path"], destination)
    return tmp_path, copy.deepcopy(manifest)


def test_real_release_inventory_passes():
    assert validate()["unique_historical_tests"] == 202


def test_content_drift_is_rejected(release_copy):
    root, manifest = release_copy
    path = root / "experiments/day62/system-prompt.md"
    path.write_text("changed policy", encoding="utf-8")
    with pytest.raises(ReleaseError, match="artifact_hash_mismatch"):
        validate(root, manifest)


def test_crlf_checkout_remains_valid(release_copy):
    root, manifest = release_copy
    path = root / "experiments/day62/system-prompt.md"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert validate(root, manifest)["status"] == "passed"


def test_removing_asset_from_manifest_does_not_hide_it(release_copy):
    root, manifest = release_copy
    manifest["artifacts"].pop()
    with pytest.raises(ReleaseError, match="artifact_inventory_mismatch"):
        validate(root, manifest)


def test_duplicate_asset_is_rejected(release_copy):
    root, manifest = release_copy
    manifest["artifacts"].append(manifest["artifacts"][0])
    with pytest.raises(ReleaseError, match="duplicate_artifact"):
        validate(root, manifest)


@pytest.mark.parametrize(
    "path", ["../outside", "C:/secrets", ".env", "experiments\\day62\\sales_prompt.py"]
)
def test_unsafe_or_out_of_scope_path_is_rejected(release_copy, path):
    root, manifest = release_copy
    manifest["artifacts"][0]["path"] = path
    with pytest.raises(ReleaseError):
        validate(root, manifest)


def test_capability_cannot_claim_business_tools(release_copy):
    root, manifest = release_copy
    manifest["capabilities"]["live_business_tools"] = "verified"
    with pytest.raises(ReleaseError, match="unsupported_capability_claim"):
        validate(root, manifest)


def test_candidate_cannot_claim_release_date(release_copy):
    root, manifest = release_copy
    manifest["release_date"] = "2026-09-21"
    with pytest.raises(ReleaseError, match="candidate_cannot_have_release_date"):
        validate(root, manifest)


def test_released_requires_date(release_copy):
    root, manifest = release_copy
    manifest["release_status"] = "released"
    with pytest.raises(ReleaseError, match="released_requires_valid_date"):
        validate(root, manifest)


def test_old_evidence_hash_cannot_be_bypassed_by_refreezing_one_file(release_copy):
    root, manifest = release_copy
    name = "experiments/day62/system-prompt.md"
    (root / name).write_text("changed policy", encoding="utf-8")
    next(item for item in manifest["artifacts"] if item["path"] == name)["sha256"] = (
        digest(root / name)
    )
    with pytest.raises(ReleaseError, match="historical_source_hash_mismatch"):
        validate(root, manifest)


@pytest.mark.parametrize(
    "counts",
    [
        {"tests": 86, "failures": 0, "errors": 0, "skipped": 23},
        {"tests": 85, "failures": 0, "errors": 0, "skipped": 0},
        {"tests": 86, "failures": 1, "errors": 0, "skipped": 0},
    ],
)
def test_incomplete_suite_is_never_accepted(counts):
    with pytest.raises(ValueError):
        require_passed(counts, 86)


def test_junit_counts_are_read_from_machine_result(tmp_path):
    path = tmp_path / "result.xml"
    path.write_text(
        '<testsuites><testsuite tests="86" failures="0" errors="0" skipped="0"/></testsuites>',
        encoding="utf-8",
    )
    require_passed(junit_counts(path), 86)
