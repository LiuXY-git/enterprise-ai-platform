"""Guard the release inventory and reject false successful acceptance reports."""

import copy
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v10_gate as gate  # noqa: E402
import verify_v10 as verifier  # noqa: E402


@pytest.fixture
def release_copy(tmp_path):
    manifests = [
        json.loads((gate.ROOT / name).read_text(encoding="utf-8"))
        for name in (
            gate.MANIFEST,
            "agent-center/release-v0.5.0.json",
            "agent-center/release-v0.2.0.json",
            "agent-center/release-v0.1.0.json",
        )
    ]
    names = {a["path"] for m in manifests for a in m["artifacts"]}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(gate.ROOT / name, path)
    return tmp_path, copy.deepcopy(manifests[0])


def test_current_release():
    result = gate.validate()
    assert result["unique_regression_tests_required"] == 677
    assert result["tests_executed_by_this_check"] == 0
    assert (
        result["v05_integrity"]["v02_and_v01_integrity"]["v01_integrity"]["status"]
        == "passed"
    )
    assert not result["remote_tag_or_release_checked"]


@pytest.mark.parametrize(
    "status,released", [("candidate", None), ("released", "2026-09-24")]
)
def test_candidate_and_released(release_copy, status, released):
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
def test_bad_status(release_copy, status, released):
    root, manifest = release_copy
    manifest.update(release_status=status, release_date=released)
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name",
    [
        "experiments/day82/prompt_policy.py",
        "docs/evidence/day82/comparison/monthly-candidate.json",
    ],
)
def test_changed_asset(release_copy, name):
    root, manifest = release_copy
    (root / name).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        gate.validate(root, manifest)


def test_crlf_portable(release_copy):
    root, manifest = release_copy
    path = root / "experiments/day82/prompt_policy.py"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert gate.validate(root, manifest)["status"] == "passed"


@pytest.mark.parametrize("kind", ["omit", "duplicate", "extra", "missing"])
def test_inventory_drift(release_copy, kind):
    root, manifest = release_copy
    if kind == "omit":
        manifest["artifacts"].pop()
    elif kind == "duplicate":
        manifest["artifacts"].append(manifest["artifacts"][0])
    elif kind == "extra":
        (root / "experiments/day82/unreviewed.py").write_text("pass", encoding="utf-8")
    else:
        (root / manifest["artifacts"][0]["path"]).unlink()
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "C:/secret",
        ".env",
        "experiments\\day75\\memory_store.py",
        "experiments/day75/../day75/memory_store.py",
    ],
)
def test_bad_paths(release_copy, name):
    root, manifest = release_copy
    manifest["artifacts"][0]["path"] = name
    with pytest.raises(ValueError):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "2.0.0"),
        ("capabilities", {"agent": "integrated"}),
        ("unique_regression_test_counts", {"day75": 999}),
        ("demo_video", {"status": "recorded"}),
    ],
)
def test_claims_cannot_drift(release_copy, field, value):
    root, manifest = release_copy
    manifest[field] = value
    with pytest.raises(ValueError, match="manifest_claim_mismatch"):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "name,error",
    [
        ("experiments/day82/prompt_policy.py", "historical_hash_mismatch"),
    ],
)
def test_refreezing_does_not_bypass_history(release_copy, name, error):
    root, manifest = release_copy
    (root / name).write_text("changed", encoding="utf-8")
    next(a for a in manifest["artifacts"] if a["path"] == name)["sha256"] = gate.digest(
        root / name
    )
    with pytest.raises(ValueError, match=error):
        gate.validate(root, manifest)


def test_old_release_still_protected(release_copy):
    root, manifest = release_copy
    (root / "experiments/day59/plan_schema.py").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "xml",
    [
        "<testsuites/>",
        '<testsuite tests="1" failures="0" errors="0" skipped="0"/>',
        '<testsuite tests="1"><testcase classname="small" name="one"/></testsuite>',
        '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase><skipped/></testcase></testsuite>',
    ],
)
def test_bad_junit(tmp_path, xml):
    path = tmp_path / "test.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        verifier.junit_counts(path)


def test_exact_pass_count(tmp_path):
    path = tmp_path / "test.xml"
    path.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="small" name="one"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    counts = verifier.junit_counts(path)
    verifier.require_passed(counts, 1)
    with pytest.raises(ValueError):
        verifier.require_passed(counts, 2)


def test_existing_output_retained(tmp_path):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        verifier.verify(tmp_path, Path(sys.executable), Path(sys.executable))
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize(
    "failure", ["exit", "timeout", "skip", "drift", "malformed_xml"]
)
def test_runner_failure_not_success(tmp_path, monkeypatch, failure):
    root = tmp_path / "repo"
    manifest = root / gate.MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr(verifier, "validate", lambda root: {"status": "passed"})
    monkeypatch.setattr(verifier, "SUITES", [("small", "runtime", 1, ["test.py"])])

    def fake_run(*args, **kwargs):
        assert "--live" not in args[0]
        if failure == "timeout":
            raise subprocess.TimeoutExpired("pytest", 300, output=b"partial")
        skipped = int(failure == "skip")
        xml = f'<testsuite tests="1" failures="0" errors="0" skipped="{skipped}"><testcase classname="small" name="one">{"<skipped/>" if skipped else ""}</testcase></testsuite>'
        (output / "small.xml").write_text(
            "<broken" if failure == "malformed_xml" else xml, encoding="utf-8"
        )
        if failure == "drift":
            manifest.write_text('{"changed":true}', encoding="utf-8")
        return SimpleNamespace(
            returncode=int(failure == "exit"), stdout="captured", stderr=""
        )

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    with pytest.raises((ValueError, ET.ParseError)):
        verifier.verify(output, Path(sys.executable), Path(sys.executable), root)
    assert (output / "small.txt").exists() and (output / "failure.json").exists()
    assert not (output / "verification.json").exists()


def test_regression_counts_are_disjoint():
    assert sum(gate.COUNTS.values()) == 677
    assert gate.COUNTS["day64"] == 141
    assert sum(s[2] for s in verifier.SUITES[:3]) == 677


@pytest.mark.parametrize(
    "field,value", [("status", "recorded"), ("recording_verified", True)]
)
def test_cannot_hide_video_deferment(release_copy, field, value):
    root, manifest = release_copy
    name = gate.DEFERRED["checklist"]
    video = json.loads((root / name).read_text(encoding="utf-8"))
    video[field] = value
    (root / name).write_text(json.dumps(video), encoding="utf-8")
    next(a for a in manifest["artifacts"] if a["path"] == name)["sha256"] = gate.digest(
        root / name
    )
    with pytest.raises(ValueError, match="demo_status_mismatch"):
        gate.validate(root, manifest)


@pytest.mark.parametrize(
    "body",
    [
        "<testcase/><testcase/>",
        '<testcase classname="x" name="one"/><testcase classname="x" name="one"/>',
    ],
)
def test_junit_requires_unique_identity(tmp_path, body):
    path = tmp_path / "duplicate.xml"
    path.write_text(
        '<testsuite tests="2" failures="0" errors="0" skipped="0">'
        + body
        + "</testsuite>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing_or_duplicate_test_identity"):
        verifier.junit_counts(path)


@pytest.mark.parametrize("overlap", [False, True])
def test_cross_suite_identity_check_and_success(tmp_path, monkeypatch, overlap):
    root = tmp_path / "repo"
    manifest = root / gate.MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    output = tmp_path / "out"
    monkeypatch.setattr(verifier, "validate", lambda root: {"status": "passed"})
    monkeypatch.setattr(
        verifier,
        "SUITES",
        [(name, "runtime", 1, ["test.py"]) for name in ("first", "second")],
    )

    def fake_run(command, **kwargs):
        report = Path(
            next(
                arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml=")
            )
        )
        name = "same" if overlap else report.stem
        report.write_text(
            f'<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="x" name="{name}"/></testsuite>',
            encoding="utf-8",
        )
        assert (
            "--live" not in command
            and kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        )
        return SimpleNamespace(returncode=0, stdout="passed", stderr="")

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    if overlap:
        with pytest.raises(ValueError, match="overlapping_test_suites"):
            verifier.verify(output, Path(sys.executable), Path(sys.executable), root)
        assert (output / "failure.json").exists()
        assert not (output / "verification.json").exists()
    else:
        result = verifier.verify(
            output, Path(sys.executable), Path(sys.executable), root
        )
        assert result["total_tests"] == 2 and result["demo_video_status"] == "deferred"
        assert set(result["output_hashes"]) == {
            "first.txt",
            "first.xml",
            "second.txt",
            "second.xml",
        }


def test_missing_interpreter_produces_failure_record(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    manifest = root / gate.MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(verifier, "validate", lambda root: {"status": "passed"})
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="missing_python_environment"):
        verifier.verify(output, tmp_path / "missing", Path(sys.executable), root)
    assert (output / "failure.json").exists()
    assert not (output / "verification.json").exists()
