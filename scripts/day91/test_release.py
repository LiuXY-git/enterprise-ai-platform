"""Release inventory, provenance, acceptance completeness and publication boundaries."""

import shutil
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.day86.dataset_tool import read_json  # noqa: E402
from experiments.day87.runner import atomic_save  # noqa: E402
from scripts.day91 import (  # noqa: E402
    release_gate as gate,
)  # noqa: E402
from scripts.day91 import (  # noqa: E402
    release_notes as notes,
)
from scripts.day91 import (  # noqa: E402
    verify_release as verifier,
)


@pytest.fixture
def release_copy(tmp_path):
    manifest = read_json(ROOT / gate.MANIFEST)
    names = {a["path"] for a in manifest["artifacts"]} | {gate.MANIFEST}
    for version in ["1.0.0", "0.5.0", "0.2.0", "0.1.0"]:
        name = f"agent-center/release-v{version}.json"
        names.add(name)
        names.update(a["path"] for a in read_json(ROOT / name)["artifacts"])
    root = tmp_path / "repo"
    for name in names:
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    return root, manifest


def rehash(root, manifest, name):
    next(a for a in manifest["artifacts"] if a["path"] == name)["sha256"] = gate.digest(
        root / name
    )


def test_current_candidate_or_release():
    result = gate.validate()
    assert result["unique_regression_tests_required"] == 342
    assert result["tests_executed_by_this_check"] == 0
    assert result["historical_fixture_score"]["passed"] == 12
    assert result["parent_agent_integrity"]["status"] == "passed"
    assert result["remote_tag_or_release_checked"] is False


@pytest.mark.parametrize(
    "status,day", [("candidate", None), ("released", "2026-09-30")]
)
def test_supported_release_states(release_copy, status, day):
    root, manifest = release_copy
    manifest.update(release_status=status, release_date=day)
    assert gate.validate(root, manifest)["release_status"] == status


@pytest.mark.parametrize(
    "status,day",
    [
        ("candidate", "2026-09-30"),
        ("released", None),
        ("released", "2026-02-30"),
        ("released", "20260930"),
        ("published", None),
    ],
)
def test_bad_release_states(release_copy, status, day):
    root, manifest = release_copy
    manifest.update(release_status=status, release_date=day)
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


@pytest.mark.parametrize("kind", ["omit", "duplicate", "extra", "changed", "missing"])
def test_inventory_drift(release_copy, kind):
    root, manifest = release_copy
    if kind == "omit":
        manifest["artifacts"].pop()
    elif kind == "duplicate":
        manifest["artifacts"].append(deepcopy(manifest["artifacts"][0]))
    elif kind == "extra":
        (root / "experiments/day90/extra.py").write_text("pass")
    elif kind == "changed":
        (root / "experiments/day90/scoring.py").write_text("pass")
    else:
        (root / manifest["artifacts"][0]["path"]).unlink()
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "/absolute",
        "C:/absolute",
        "experiments\\day90\\scoring.py",
        "experiments/../file",
    ],
)
def test_invalid_paths(tmp_path, name):
    with pytest.raises(ValueError):
        gate.safe_path(tmp_path, name)


def test_historical_source_rehash_does_not_hide_change(release_copy):
    root, manifest = release_copy
    name = "experiments/day90/scoring.py"
    with (root / name).open("a") as stream:
        stream.write("\n# changed\n")
    rehash(root, manifest, name)
    with pytest.raises(ValueError, match="historical_source_mismatch"):
        gate.validate(root, manifest)


def test_historical_evidence_rehash_does_not_hide_change(release_copy):
    root, manifest = release_copy
    name = "docs/evidence/day90/cases/monthly_normal/events.json"
    data = read_json(root / name)
    data["task"]["status"] = "failed"
    atomic_save(root / name, data)
    rehash(root, manifest, name)
    with pytest.raises(ValueError, match="historical_evidence_mismatch"):
        gate.validate(root, manifest)


def test_parent_integrity_still_enforced(release_copy):
    root, manifest = release_copy
    name = "demo/day83/recording-status.json"
    (root / name).write_text("{}")
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


def test_navigation_exclusion_is_specific(release_copy):
    root, manifest = release_copy
    name = "docs/evidence/day85/validation.json"
    record = read_json(root / name)
    record["source_sha256_lf"]["evaluation-center/README.md"] = "0" * 64
    atomic_save(root / name, record)
    rehash(root, manifest, name)
    with pytest.raises(ValueError, match="excluded_history_changed"):
        gate.validate(root, manifest)


def test_capability_cannot_claim_live_evaluation(release_copy):
    root, manifest = release_copy
    manifest["capabilities"]["live_model_evaluation"] = "implemented"
    with pytest.raises(ValueError, match="manifest_claim_mismatch"):
        gate.validate(root, manifest)


def test_crlf_portability(release_copy):
    root, manifest = release_copy
    path = root / "experiments/day90/runner.py"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert gate.validate(root, manifest)["status"] == "passed"


def test_candidate_cannot_generate_formal_notes(release_copy, tmp_path):
    root, manifest = release_copy
    manifest.update(release_status="candidate", release_date=None)
    atomic_save(root / gate.MANIFEST, manifest)
    directory = tmp_path / "candidate"
    directory.mkdir()
    atomic_save(
        directory / "verification.json",
        dict(status="passed", release_status="candidate"),
    )
    with pytest.raises(ValueError, match="formal_released_acceptance_required"):
        notes.acceptance(directory, root)


def test_notes_preserve_existing_file(tmp_path):
    output = tmp_path / "release-body.md"
    output.write_text("keep")
    with pytest.raises(FileExistsError):
        notes.create(tmp_path, output)
    assert output.read_text() == "keep"


@pytest.fixture
def fake_acceptance(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "evaluation-center").mkdir(parents=True)
    (root / gate.MANIFEST).write_text("{}")
    monkeypatch.setattr(
        gate, "validate", lambda root: dict(status="passed", release_status="candidate")
    )
    monkeypatch.setattr(
        verifier,
        "SUITES",
        (("regression", 1, ["test_a.py"]), ("release", 1, ["test_b.py"])),
    )
    sample = read_json(ROOT / "docs/evidence/day90/scoring.json")
    monkeypatch.setattr(
        verifier.scoring, "inspect", lambda *args: dict(summary=sample["summary"])
    )

    def execute(command, directory, root, timeout=900):
        if "-m" in command:
            xml = directory / "tests.xml"
            xml.write_text(
                f'<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="unit" name="{directory.name}"/></testsuite>'
            )
        else:
            (directory / "full/evaluation").mkdir(parents=True)
            atomic_save(directory / "full/evaluation/report.json", sample)

    monkeypatch.setattr(verifier, "execute", execute)
    return root, tmp_path / "output", sample, execute


def test_verifier_success_uses_all_suites_and_fresh_run(fake_acceptance):
    root, output, _, _ = fake_acceptance
    result = verifier.verify(output, sys.executable, root)
    assert result["total_tests"] == 2 and result["fixture_cases"] == 12
    assert result["new_model_requests"] == 0
    assert set(result["output_sha256_lf"]) == {
        "regression/tests.xml",
        "release/tests.xml",
        "integration/full/evaluation/report.json",
    }


@pytest.mark.parametrize(
    "fault",
    ["suite_exit", "skipped", "duplicate", "partial", "usage", "manifest_change"],
)
def test_verifier_rejects_false_success(fake_acceptance, monkeypatch, fault):
    root, output, sample, execute = fake_acceptance

    def bad(command, directory, root, timeout=900):
        execute(command, directory, root, timeout)
        if directory.name == "release":
            if fault == "suite_exit":
                raise ValueError("injected_exit")
            if fault == "skipped":
                (directory / "tests.xml").write_text(
                    '<testsuite tests="1" failures="0" errors="0" skipped="1"><testcase classname="unit" name="release"><skipped/></testcase></testsuite>'
                )
            if fault == "duplicate":
                shutil.copyfile(
                    output / "regression/tests.xml", directory / "tests.xml"
                )
        if directory.name == "integration":
            if fault == "partial":
                sample["full_dataset_evaluated"] = False
            if fault == "usage":
                sample["source"]["usage"]["summary"]["input_tokens"] = 0
            if fault == "manifest_change":
                (root / gate.MANIFEST).write_text('{"changed":true}')
            atomic_save(directory / "full/evaluation/report.json", sample)

    monkeypatch.setattr(verifier, "execute", bad)
    with pytest.raises(ValueError):
        verifier.verify(output, sys.executable, root)
    assert (output / "failure.json").exists() and not (
        output / "verification.json"
    ).exists()


def test_verifier_preserves_output(fake_acceptance):
    root, output, _, _ = fake_acceptance
    output.mkdir()
    (output / "marker").write_text("keep")
    with pytest.raises(FileExistsError):
        verifier.verify(output, sys.executable, root)
    assert (output / "marker").read_text() == "keep"


def test_missing_python_records_failure(fake_acceptance):
    root, output, _, _ = fake_acceptance
    with pytest.raises(ValueError, match="python_environment_missing"):
        verifier.verify(output, output / "missing.exe", root)
    assert (output / "failure.json").exists()


@pytest.fixture
def formal_acceptance(fake_acceptance, monkeypatch):
    root, output, _, _ = fake_acceptance
    record = verifier.verify(output, sys.executable, root)
    manifest = dict(
        release_status="released",
        release_date="2026-09-30",
        component_tag="evaluation-center-v0.1.0",
    )
    atomic_save(root / gate.MANIFEST, manifest)
    record.update(
        release_status="released", manifest_sha256_lf=gate.digest(root / gate.MANIFEST)
    )
    atomic_save(output / "verification.json", record)
    monkeypatch.setattr(notes, "SUITES", verifier.SUITES)

    def fake_git(root, *args):
        if args[0] == "status":
            return ""
        if args[0] == "rev-parse":
            return "1" * 40
        if args[0] == "show":
            return (root / gate.MANIFEST).read_text(encoding="utf-8").strip()
        raise AssertionError("unexpected_git_operation")

    monkeypatch.setattr(notes, "git", fake_git)
    return root, output, record


@pytest.mark.parametrize(
    "fault", ["stale_manifest", "changed_output", "wrong_count", "wrong_score"]
)
def test_notes_reject_invalid_acceptance(formal_acceptance, fault):
    root, directory, record = formal_acceptance
    if fault == "stale_manifest":
        record["manifest_sha256_lf"] = "0" * 64
    if fault == "changed_output":
        (directory / "release/tests.xml").write_text("<wrong/>")
    if fault == "wrong_count":
        record["total_tests"] = 999
    if fault == "wrong_score":
        record["scoring_summary"] = {}
    atomic_save(directory / "verification.json", record)
    with pytest.raises(ValueError):
        notes.acceptance(directory, root)


def test_notes_bind_commit_date_and_manifest(formal_acceptance, tmp_path):
    root, directory, record = formal_acceptance
    output = tmp_path / "release-body.md"
    result = notes.create(directory, output, root)
    text = output.read_text(encoding="utf-8")
    assert result["tag"] == "evaluation-center-v0.1.0"
    assert (
        "1" * 40 in text
        and "2026-09-30" in text
        and record["manifest_sha256_lf"] in text
    )
    assert "填写" not in text


def test_notes_require_committed_worktree(formal_acceptance, tmp_path, monkeypatch):
    root, directory, _ = formal_acceptance
    monkeypatch.setattr(
        notes, "git", lambda *args: " M evaluation-center/release-v0.1.0.json"
    )
    with pytest.raises(ValueError, match="commit_formal_manifest_first"):
        notes.create(directory, tmp_path / "notes.md", root)
