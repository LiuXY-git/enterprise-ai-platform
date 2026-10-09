"""Failure-preserving regression orchestration and real pytest subprocess controls."""

import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import test_platform as runner
from scripts.evidence_layout.test_layout import bundle

ROOT = Path(__file__).resolve().parents[1]


def artifacts(folder, *, failures=0, errors=0, skipped=0, tests=2, code=0):
    folder.mkdir(parents=True, exist_ok=True)
    suite = ET.Element(
        "testsuite",
        {
            k: str(v)
            for k, v in dict(
                tests=tests, failures=failures, errors=errors, skipped=skipped
            ).items()
        },
    )
    for n in range(tests):
        case = ET.SubElement(
            suite, "testcase", classname="test_sample", name=f"test_{n}"
        )
        for tag, count in (
            ("failure", failures),
            ("error", errors),
            ("skipped", skipped),
        ):
            if n < count:
                ET.SubElement(case, tag)
    ET.ElementTree(suite).write(folder / "tests.xml", encoding="utf-8")
    ids = [f"tests/test_sample.py::test_{n}" for n in range(tests)]
    runner.save(
        folder / "inventory.json",
        {
            "collected": ids,
            "executed": ids,
            "exit_code": code,
            "python_version": "fixture",
            "pytest_version": "fixture",
        },
    )
    return ids


def test_clean_environment_keeps_os_but_not_credentials_or_test_overrides(monkeypatch):
    monkeypatch.setattr(
        os,
        "environ",
        {
            "Path": "os-path",
            "SYSTEMROOT": "os-root",
            "TEMP": "temp",
            "DASHSCOPE_API_KEY": "private",
            "EAP_ENV_FILE": "private.env",
            "PYTHONPATH": "injection",
            "PYTEST_ADDOPTS": "-k one",
            "PYTEST_PLUGINS": "injection",
            "LANGSMITH_API_KEY": "private",
            "HTTP_PROXY": "private",
            "AWS_SECRET_ACCESS_KEY": "private",
        },
    )
    env = runner.clean_environment()
    assert env["Path"] == "os-path" and env["SYSTEMROOT"] == "os-root"
    assert not any(
        v in {"private", "private.env", "injection", "-k one"} for v in env.values()
    )
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["LANGSMITH_TRACING"] == "false"


@pytest.mark.parametrize("selection", [["all", "api"], ["api", "api"], ["unknown"]])
def test_invalid_selection_is_rejected(selection):
    with pytest.raises(ValueError):
        runner.selected_suites(selection)


def test_selection_is_stable_and_scope_does_not_overlap():
    assert runner.selected_suites(["evaluation", "api"]) == ["api", "evaluation"]
    seen = set()
    for _, paths in runner.SUITES.values():
        for path in paths:
            assert not any(
                path.startswith(p + "/") or p.startswith(path + "/") or p == path
                for p in seen
            )
            seen.add(path)


def test_passing_requires_both_junit_and_complete_inventory(tmp_path):
    ids = artifacts(tmp_path)
    result = runner.assess(tmp_path, {"exit_code": 0})
    assert result["status"] == "passed" and result["test_ids"] == ids
    assert result["counts"]["tests"] == 2


@pytest.mark.parametrize(
    "values",
    [
        {"failures": 1, "code": 1},
        {"errors": 1, "code": 1},
        {"skipped": 1},
        {"tests": 0, "code": 5},
        {"code": 1},
    ],
)
def test_unsuccessful_runs_never_pass(tmp_path, values):
    artifacts(tmp_path, **values)
    result = runner.assess(tmp_path, {"exit_code": values.get("code", 0)})
    assert result["status"] == "failed"
    assert result["counts"]["tests"] == values.get("tests", 2)
    if values.get("failures"):
        assert result["unsuccessful"] == [
            {"id": "test_sample::test_0", "outcome": "failure"}
        ]


@pytest.mark.parametrize(
    "mutation", ["missing", "invalid", "duplicate", "count", "nested"]
)
def test_junit_corruption_is_rejected(tmp_path, mutation):
    artifacts(tmp_path)
    path = tmp_path / "tests.xml"
    if mutation == "missing":
        path.unlink()
    elif mutation == "invalid":
        path.write_text("broken")
    else:
        tree = ET.parse(path)
        node = tree.getroot()
        if mutation == "duplicate":
            node[1].set("name", node[0].get("name"))
        elif mutation == "count":
            node.set("tests", "3")
        else:
            ET.SubElement(node, "testsuite")
        tree.write(path)
    assert (
        "missing_or_invalid_junit"
        in runner.assess(tmp_path, {"exit_code": 0})["problems"]
    )


@pytest.mark.parametrize(
    "mutation", ["missing", "invalid", "empty", "duplicate", "partial", "extra", "exit"]
)
def test_incomplete_collection_or_execution_is_rejected(tmp_path, mutation):
    artifacts(tmp_path)
    path = tmp_path / "inventory.json"
    data = json.loads(path.read_text())
    if mutation == "missing":
        path.unlink()
    elif mutation == "invalid":
        path.write_text("[]")
    else:
        if mutation == "empty":
            data["collected"] = []
        elif mutation == "duplicate":
            data["collected"][1] = data["collected"][0]
        elif mutation == "partial":
            data["executed"].pop()
        elif mutation == "extra":
            data["executed"].append("extra")
        else:
            data["exit_code"] = 9
        runner.save(path, data)
    result = runner.assess(tmp_path, {"exit_code": 0})
    assert result["status"] == "failed"
    assert "missing_or_incomplete_inventory" in result["problems"]


@pytest.mark.parametrize("problem", ["timeout", "interrupted"])
def test_timeout_or_interrupt_does_not_pass_even_if_xml_looks_successful(
    tmp_path, problem
):
    artifacts(tmp_path)
    result = runner.assess(
        tmp_path, {"exit_code": 0, "problem": problem, "cleanup_verified": False}
    )
    assert result["status"] == "failed"
    assert "child_cleanup_unverified" in result["problems"]


def test_output_is_never_overwritten(tmp_path):
    (tmp_path / "summary.json").write_text("existing evidence")
    with pytest.raises(FileExistsError):
        runner.run(ROOT, tmp_path, ["api"], {})
    assert (tmp_path / "summary.json").read_text() == "existing evidence"


def test_missing_interpreters_save_each_failure_without_starting(monkeypatch, tmp_path):
    def forbidden(*a, **kw):
        pytest.fail("A missing interpreter must not start a process")

    monkeypatch.setattr(runner, "execute", forbidden)
    result = runner.run(
        ROOT,
        tmp_path / "results",
        ["api", "planner"],
        {"api": tmp_path / "absent1", "planner": tmp_path / "absent2"},
    )
    assert result["status"] == "failed"
    assert all(
        s["problems"] == ["python_environment_missing"] for s in result["suites"]
    )
    assert (
        json.loads((tmp_path / "results/summary.json").read_text())["status"]
        == "failed"
    )


def test_test_failure_does_not_hide_later_suite_results(monkeypatch, tmp_path):
    @contextmanager
    def copied(root):
        yield root

    monkeypatch.setattr(runner, "workspace", copied)
    monkeypatch.setattr(runner, "source_hashes", lambda root: {})

    def execute(command, root, folder, timeout):
        code = 1 if folder.name == "api" else 0
        artifacts(folder, failures=code, code=code)
        data = json.loads((folder / "inventory.json").read_text())
        data["collected"] = [folder.name + "/" + v for v in data["collected"]]
        data["executed"] = data["collected"]
        runner.save(folder / "inventory.json", data)
        return {"exit_code": code}

    monkeypatch.setattr(runner, "execute", execute)
    result = runner.run(
        ROOT,
        tmp_path / "results",
        ["api", "planner"],
        {"api": sys.executable, "planner": sys.executable},
    )
    assert [s["status"] for s in result["suites"]] == ["failed", "passed"]
    assert result["observed_counts"] == dict(tests=4, failures=1, errors=0, skipped=0)


def test_unverified_cleanup_stops_remaining_suites(monkeypatch, tmp_path):
    @contextmanager
    def copied(root):
        yield root

    monkeypatch.setattr(runner, "workspace", copied)
    monkeypatch.setattr(runner, "source_hashes", lambda root: {})
    monkeypatch.setattr(
        runner,
        "execute",
        lambda *a: {"exit_code": None, "problem": "timeout", "cleanup_verified": False},
    )
    result = runner.run(
        ROOT,
        tmp_path / "results",
        ["api", "planner"],
        {"api": sys.executable, "planner": sys.executable},
    )
    assert [s["status"] for s in result["suites"]] == ["failed", "not_run"]
    assert result["status"] == "failed"


def test_duplicate_suite_execution_is_reported(monkeypatch, tmp_path):
    @contextmanager
    def copied(root):
        yield root

    monkeypatch.setattr(runner, "workspace", copied)
    monkeypatch.setattr(runner, "source_hashes", lambda root: {})

    def execute(command, root, folder, timeout):
        artifacts(folder)
        return {"exit_code": 0}

    monkeypatch.setattr(runner, "execute", execute)
    result = runner.run(
        ROOT,
        tmp_path / "results",
        ["api", "planner"],
        {"api": sys.executable, "planner": sys.executable},
    )
    assert result["status"] == "failed" and result["unique_executed_tests"] == 2
    assert "overlapping_test_suites" in result["suites"][1]["problems"]


def fixture_project(root):
    bundle(root)
    (root / "tests").mkdir()
    target = root / "scripts/testing"
    target.mkdir()
    for name in ("__init__.py", "inventory.py"):
        shutil.copyfile(ROOT / "scripts/testing" / name, target / name)
    (root / ".env").write_text("DASHSCOPE_API_KEY=private-source-marker")
    return root


@pytest.mark.parametrize(
    "body,expected",
    [
        ("def test_ok(): assert 1 == 1", "passed"),
        ("def test_failure(): assert False, 'intentional-control'", "failed"),
        (
            "import pytest\ndef test_skip(): pytest.skip('intentional-control')",
            "failed",
        ),
    ],
)
def test_real_pytest_child_preserves_evidence_and_isolates_source(
    monkeypatch, tmp_path, body, expected
):
    root = fixture_project(tmp_path / "project with spaces")
    (root / "tests/test_control.py").write_text(body + "\n", encoding="utf-8")
    (root / "tests/test_isolation.py").write_text(
        "import os\nfrom pathlib import Path\ndef test_isolation():\n"
        "    assert not (Path.cwd() / '.env').exists()\n"
        "    assert 'PRIVATE_DAY96_KEY' not in os.environ\n"
        "    assert 'PYTEST_ADDOPTS' not in os.environ\n"
        "    (Path.cwd() / 'runtime-created.txt').write_text('fixture')\n"
    )
    monkeypatch.setenv("PRIVATE_DAY96_KEY", "private-env-marker")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k cannot_select_tests")
    output = tmp_path / "results with spaces"
    result = runner.run(root, output, ["api"], {"api": sys.executable}, 30)
    assert result["status"] == expected, result
    assert result["observed_counts"]["tests"] == 2
    assert (root / ".env").read_text() == "DASHSCOPE_API_KEY=private-source-marker"
    assert not (root / "runtime-created.txt").exists()
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in {".log", ".json", ".xml"}:
            assert b"private-source-marker" not in path.read_bytes()
            assert b"private-env-marker" not in path.read_bytes()
    assert (output / "api/tests.xml").is_file()
    assert (output / "api/stdout.log").is_file()
    if expected == "failed":
        assert result["suites"][0]["unsuccessful"]


def test_real_child_timeout_saves_partial_output_and_stops(tmp_path):
    result = runner.execute(
        [
            sys.executable,
            "-u",
            "-c",
            "import time; print('started', flush=True); time.sleep(30)",
        ],
        tmp_path,
        tmp_path,
        1,
    )
    assert result["problem"] == "timeout"
    assert result["cleanup_verified"] is True
    assert result["exit_code"] is not None
    assert b"started" in (tmp_path / "stdout.log").read_bytes()


def test_stop_tree_fallback_does_not_claim_verified(monkeypatch):
    calls = []
    process = SimpleNamespace(
        pid=123,
        poll=lambda: None,
        kill=lambda: calls.append("kill"),
        wait=lambda **kw: calls.append("wait"),
    )

    def fail(*args, **kwargs):
        raise OSError("fixture cleanup denied")

    if os.name == "nt":
        monkeypatch.setattr(subprocess, "run", fail)
    else:
        monkeypatch.setattr(os, "killpg", fail)
    assert runner.stop_tree(process) is False
    assert calls == ["kill", "wait"]


@pytest.mark.parametrize("relative", ["tests/results", "scripts/results", "."])
def test_output_cannot_pollute_source_collection(tmp_path, relative):
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(ValueError, match="repository_output"):
        runner.run(root, root / relative, ["api"], {})
    assert not list(root.iterdir())
