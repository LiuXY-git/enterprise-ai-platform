"""Release failures must never produce passing acceptance or release notes."""

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.release import verify_platform as release


def write_manifest(root, manifest):
    target = root / release.MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for name in release.ROOT_FILES:
        (root / name).write_text("fixture\n", encoding="utf-8")
    (root / "frontend").mkdir()
    (root / "frontend/app.js").write_text("console.log('fixture');\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "product": "Enterprise AI Platform",
        "version": "1.0.0",
        "tag": release.TAG,
        "hash_policy": "sha256_crlf_to_lf_except_zip",
        "release_status": "candidate",
        "released_on": None,
        "expected_tests": {**release.MINIMUM_TESTS, "release": 1},
        "files": release.inventory(root),
    }
    write_manifest(root, manifest)
    return root, manifest


@pytest.mark.parametrize("action", ["modify", "add", "remove", "manifest_remove_entry"])
def test_source_change_fails(project, action):
    root, manifest = project
    path = root / "frontend/app.js"
    if action == "modify":
        path.write_text("changed", encoding="utf-8")
    elif action == "add":
        (root / "frontend/new.js").write_text("new", encoding="utf-8")
    elif action == "remove":
        path.unlink()
    else:
        manifest["files"].pop("frontend/app.js")
        write_manifest(root, manifest)
    with pytest.raises(ValueError, match="release_inventory_mismatch"):
        release.check(root)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tag", "v1.0.0"),
        ("product", "Agent Center"),
        ("version", "0.1.0"),
        ("schema_version", 2),
        ("hash_policy", "raw"),
        ("release_status", "passed"),
        ("released_on", "2026-10-09"),
    ],
)
def test_bad_identity_or_status(project, field, value):
    root, manifest = project
    manifest[field] = value
    write_manifest(root, manifest)
    with pytest.raises(ValueError):
        release.check(root)


@pytest.mark.parametrize("released", [None, "2026-02-30", "20261009", ""])
def test_bad_formal_date(project, released):
    root, manifest = project
    manifest.update(release_status="released", released_on=released)
    write_manifest(root, manifest)
    with pytest.raises(ValueError):
        release.check(root)


@pytest.mark.parametrize(
    "status,day", [("candidate", None), ("released", "2026-10-09")]
)
def test_valid_status(project, status, day):
    root, manifest = project
    manifest.update(release_status=status, released_on=day)
    write_manifest(root, manifest)
    assert release.check(root)["release_status"] == status


def test_private_and_runtime_files_not_in_inventory(project):
    root, original = project
    for name in [
        ".env",
        ".env.local",
        "backend/.env.private",
        "logs/a.json",
        "data/a.json",
        "frontend/node_modules/a.js",
        "backend/.venv/a.py",
        "docs/evidence/week-14.md",
        "scripts/evidence_layout/index.json",
    ]:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("PRIVATE_SENTINEL", encoding="utf-8")
    assert release.inventory(root) == original["files"]


def test_crlf_normalized_and_zip_bytes_preserved(tmp_path):
    text = tmp_path / "a.md"
    text.write_bytes(b"line\n")
    expected = release.digest(text)
    text.write_bytes(b"line\r\n")
    assert release.digest(text) == expected
    binary = tmp_path / "a.zip"
    binary.write_bytes(b"line\r\n")
    assert release.digest(binary) != expected


@pytest.mark.parametrize("problem", ["missing", "extra", "bool", "too_small"])
def test_incomplete_test_contract(project, problem):
    root, manifest = project
    if problem == "missing":
        manifest["expected_tests"].pop("agent")
    elif problem == "extra":
        manifest["expected_tests"]["unknown"] = 1
    elif problem == "bool":
        manifest["expected_tests"]["release"] = True
    else:
        manifest["expected_tests"]["api"] = 617
    write_manifest(root, manifest)
    with pytest.raises(ValueError, match="invalid_test_contract"):
        release.check(root)


@pytest.mark.parametrize("failure", ["failures", "errors", "skipped", "tests"])
def test_counts_must_match_and_all_pass(failure):
    counts = dict(tests=10, failures=0, errors=0, skipped=0)
    counts[failure] += 1
    with pytest.raises(ValueError, match="unexpected_test_counts"):
        release.require_counts(counts, 10)


@pytest.fixture
def simulated(project, monkeypatch, tmp_path):
    root, manifest = project
    identity = {"commit": "a" * 40, "working_tree_clean": True}
    monkeypatch.setattr(release, "git_identity", lambda root: deepcopy(identity))

    def assessed(name, count):
        return {
            "status": "passed",
            "counts": dict(tests=count, failures=0, errors=0, skipped=0),
            "test_ids": [f"{name}::{i}" for i in range(count)],
            "exit_code": 0,
        }

    control = assessed("release", 1)
    monkeypatch.setattr(release, "release_tests", lambda *a: deepcopy(control))
    regression = {
        "status": "passed",
        "selected_suites": list(release.runner.SUITES),
        "suites": [{"suite": name, "exit_code": 0} for name in release.runner.SUITES],
    }

    def run(*a):
        return deepcopy(regression)

    monkeypatch.setattr(release.runner, "run", run)
    monkeypatch.setattr(
        release.runner,
        "assess",
        lambda folder, execution: assessed(
            folder.name, manifest["expected_tests"][folder.name]
        ),
    )
    return dict(
        root=root,
        manifest=manifest,
        identity=identity,
        control=control,
        regression=regression,
        output=tmp_path / "result",
        interpreters={k: Path(sys.executable) for k in ("api", "planner", "runtime")},
    )


def execute(state):
    return release.verify(state["root"], state["output"], state["interpreters"])


@pytest.mark.parametrize("formal", [False, True])
def test_candidate_and_clean_formal_acceptance_generate_notes(simulated, formal):
    state = simulated
    if formal:
        state["manifest"].update(release_status="released", released_on="2026-10-09")
        write_manifest(state["root"], state["manifest"])
    result = execute(state)
    assert result["status"] == "passed"
    assert result["total_tests"] == sum(state["manifest"]["expected_tests"].values())
    body = (state["output"] / "release-body.md").read_text(encoding="utf-8")
    assert release.TAG in body and "真实模型成功率" in body
    assert ("正式定版验收" if formal else "候选验收") in body


@pytest.mark.parametrize(
    "failure",
    [
        "missing_python",
        "dirty_formal",
        "no_git_formal",
        "controls",
        "regression",
        "missing_suite",
        "wrong_counts",
        "duplicate_ids",
        "source_changed",
        "interrupt",
    ],
)
def test_failed_run_saves_failure_without_notes(simulated, monkeypatch, failure):
    state = simulated
    if failure == "missing_python":
        state["interpreters"]["api"] = state["root"] / "missing.exe"
    elif failure in {"dirty_formal", "no_git_formal"}:
        state["manifest"].update(release_status="released", released_on="2026-10-09")
        write_manifest(state["root"], state["manifest"])
        state["identity"].update(
            working_tree_clean=False if failure == "dirty_formal" else True,
            commit=None if failure == "no_git_formal" else "a" * 40,
        )
    elif failure == "controls":
        state["control"]["status"] = "failed"
    elif failure == "regression":
        state["regression"]["status"] = "failed"
    elif failure == "missing_suite":
        state["regression"]["suites"].pop()
    elif failure == "wrong_counts":
        state["control"]["counts"]["tests"] = 0
    elif failure == "duplicate_ids":
        state["control"]["test_ids"] = ["api::0"]
    elif failure == "source_changed":

        def mutate(*args):
            (state["root"] / "frontend/app.js").write_text("changed", encoding="utf-8")
            return deepcopy(state["regression"])

        monkeypatch.setattr(release.runner, "run", mutate)
    else:

        def interrupt(*args):
            raise KeyboardInterrupt

        monkeypatch.setattr(release, "release_tests", interrupt)
    result = execute(state)
    assert result["status"] == "failed"
    assert (
        json.loads((state["output"] / "verification.json").read_text())["status"]
        == "failed"
    )
    assert not (state["output"] / "release-body.md").exists()


def test_existing_output_preserved(simulated):
    state = simulated
    state["output"].mkdir()
    marker = state["output"] / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        execute(state)
    assert marker.read_text() == "keep"


def test_repository_output_cannot_overwrite_sources(simulated):
    state = simulated
    state["output"] = state["root"] / "frontend" / "output"
    with pytest.raises(ValueError, match="repository_output"):
        execute(state)
    assert not state["output"].exists()
