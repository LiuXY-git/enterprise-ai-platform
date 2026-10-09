"""Archive preservation, rejection controls and current-code execution boundaries."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.evaluate import absolute_arguments  # noqa: E402
from scripts.evidence_layout import INDEX, read_records, workspace  # noqa: E402


def bundle(root, *, entry="docs/evidence/day92/result.json", raw=b'{"ok":true}'):
    path = root / "docs/evidence/week-14.zip"
    path.parent.mkdir(parents=True)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zipped:
        zipped.writestr(entry, raw)
    index = {
        "format_version": 1,
        "evidence_records": 1,
        "archives": [
            {
                "path": "docs/evidence/week-14.zip",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "entries": {
                    entry: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
                },
            }
        ],
    }
    destination = root / INDEX
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(index), encoding="utf-8")
    return index


def test_all_records_survive_without_loose_day_files():
    records = read_records(ROOT)
    evidence = [p for p in records if p.startswith("docs/evidence/")]
    index = json.loads((ROOT / INDEX).read_text(encoding="utf-8"))
    assert len(evidence) == index["evidence_records"]
    assert len(evidence) >= 301
    assert not list((ROOT / "docs/evidence").glob("day*"))
    result = json.loads(records["docs/evidence/day92/validation.json"])
    assert result["tests"]["backend-tests"]["tests"] == 514


def test_archive_corruption_is_rejected(tmp_path):
    bundle(tmp_path)
    with (tmp_path / "docs/evidence/week-14.zip").open("ab") as stream:
        stream.write(b"altered")
    with pytest.raises(ValueError, match="archive_hash_mismatch"):
        read_records(tmp_path)


def test_member_hash_is_checked_even_with_matching_archive(tmp_path):
    index = bundle(tmp_path)
    index["archives"][0]["entries"]["docs/evidence/day92/result.json"]["sha256"] = (
        "0" * 64
    )
    (tmp_path / INDEX).write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="record_hash_mismatch"):
        read_records(tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "../escape.json",
        "/escape.json",
        "C:/escape.json",
        "docs\\evidence\\day92\\x.json",
    ],
)
def test_unsafe_member_names_are_rejected(tmp_path, path):
    bundle(tmp_path, entry=path)
    with pytest.raises(
        ValueError, match="invalid_archive_path|archive_inventory_mismatch"
    ):
        read_records(tmp_path)


def test_wrong_week_is_rejected(tmp_path):
    bundle(tmp_path, entry="docs/evidence/day85/result.json")
    with pytest.raises(ValueError, match="evidence_week_mismatch"):
        read_records(tmp_path)


def test_missing_archive_is_not_silently_ignored(tmp_path):
    bundle(tmp_path)
    (tmp_path / "docs/evidence/week-14.zip").unlink()
    with pytest.raises(FileNotFoundError):
        read_records(tmp_path)


def test_documents_archive_cannot_replace_python(tmp_path):
    index = bundle(tmp_path, entry="scripts/runner.py", raw=b"malicious")
    old = tmp_path / "docs/evidence/week-14.zip"
    new = tmp_path / "scripts/evidence_layout/documents.zip"
    old.rename(new)
    index["archives"][0]["path"] = "scripts/evidence_layout/documents.zip"
    (tmp_path / INDEX).write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="only_contain_documents"):
        read_records(tmp_path)


def test_snapshot_uses_current_code_excludes_secrets_and_cleans_up(tmp_path):
    root = tmp_path / "source"
    bundle(root)
    code = root / "experiments/current.py"
    code.parent.mkdir()
    code.write_bytes(b"changed_current_source")
    (root / ".env").write_bytes(b"private")
    (root / "conftest.py").write_bytes(b"# current test configuration")
    (root / "data").mkdir()
    (root / "data/private.sqlite").write_bytes(b"private")
    with (
        pytest.raises(RuntimeError, match="fixture"),
        workspace(root, temporary_parent=tmp_path) as copied,
    ):
        assert (
            copied / "experiments/current.py"
        ).read_bytes() == b"changed_current_source"
        assert (copied / "docs/evidence/day92/result.json").exists()
        assert (copied / "conftest.py").read_bytes() == b"# current test configuration"
        assert not (copied / ".env").exists() and not (copied / "data").exists()
        raise RuntimeError("fixture")
    assert not copied.exists()
    assert not (root / "docs/evidence/day92").exists()


def test_output_and_input_paths_stay_outside_disposable_workspace(tmp_path):
    args = absolute_arguments(
        ["grade", "--input-dir", "run", "--output-dir=report"], tmp_path
    )
    assert args == [
        "grade",
        "--input-dir",
        str(tmp_path / "run"),
        "--output-dir=" + str(tmp_path / "report"),
    ]


def test_restored_layout_passes_and_code_corruption_still_fails(tmp_path):
    with workspace(ROOT, temporary_parent=tmp_path) as copied:
        command = [sys.executable, "-B", "-m", "scripts.day91.release_gate"]
        result = subprocess.run(
            command, cwd=copied, capture_output=True, text=True, encoding="utf-8"
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["status"] == "passed"
        path = copied / "backend/app/settings.py"
        with path.open("ab") as stream:
            stream.write(b"\n# corrupt current source\n")
        result = subprocess.run(
            command, cwd=copied, capture_output=True, text=True, encoding="utf-8"
        )
        assert result.returncode != 0
