"""Validated weekly evidence archives and temporary execution workspaces."""

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

INDEX = "scripts/evidence_layout/index.json"
SKIP = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}
SOURCE_DIRS = {
    "backend",
    "experiments",
    "scripts",
    "agent-center",
    "evaluation-center",
    "demo",
    "n8n",
    "docs",
    "tests",
}
MAX_RECORD = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _relative(name):
    if not isinstance(name, str) or not name:
        raise ValueError("invalid_archive_path")
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or ":" in name
        or path.as_posix() != name
    ):
        raise ValueError("invalid_archive_path")
    return path


def read_records(root):
    """Check every archive and entry before returning any bytes for extraction."""
    root = Path(root).resolve()
    index = json.loads((root / INDEX).read_text(encoding="utf-8"))
    if index.get("format_version") != 1 or not isinstance(index.get("archives"), list):
        raise ValueError("unsupported_evidence_layout")
    result, names, archive_names = {}, set(), set()
    total = evidence_count = 0
    for archive in index["archives"]:
        name = archive["path"]
        _relative(name)
        match = re.fullmatch(r"docs/evidence/week-(\d{2})\.zip", name)
        documents = name == "scripts/evidence_layout/documents.zip"
        if not (match or documents) or name in archive_names:
            raise ValueError("invalid_archive_inventory")
        archive_names.add(name)
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("archive_escapes_repository")
        if (
            path.stat().st_size > MAX_TOTAL
            or _digest(path.read_bytes()) != archive["sha256"]
        ):
            raise ValueError("archive_hash_mismatch")
        entries = archive["entries"]
        with ZipFile(path) as zipped:
            members = zipped.infolist()
            if len(members) != len(entries) or {m.filename for m in members} != set(
                entries
            ):
                raise ValueError("archive_inventory_mismatch")
            for member in members:
                relative = _relative(member.filename)
                if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("archive_entry_not_regular_file")
                folded = member.filename.casefold()
                if folded in names:
                    raise ValueError("duplicate_archive_entry")
                names.add(folded)
                if documents:
                    if relative.suffix != ".md" or member.filename.startswith(
                        "docs/evidence/"
                    ):
                        raise ValueError(
                            "compatibility_archive_must_only_contain_documents"
                        )
                else:
                    day = re.match(r"docs/evidence/day(\d+)/", member.filename)
                    if not day or (int(day[1]) - 1) // 7 + 1 != int(match[1]):
                        raise ValueError("evidence_week_mismatch")
                    evidence_count += 1
                expected = entries[member.filename]
                total += member.file_size
                if (
                    not 0 <= member.file_size <= MAX_RECORD
                    or total > MAX_TOTAL
                    or member.file_size != expected["size"]
                ):
                    raise ValueError("archive_size_invalid")
                raw = zipped.read(member)
                if _digest(raw) != expected["sha256"]:
                    raise ValueError("record_hash_mismatch")
                result[member.filename] = raw
    if evidence_count != index.get("evidence_records"):
        raise ValueError("evidence_count_mismatch")
    return result


def _copy_sources(root, destination):
    """Copy present source files, including edits, without Git, secrets or runtime data."""
    for current, dirs, files in os.walk(root, followlinks=False):
        current = Path(current)
        relative_dir = current.relative_to(root)
        if relative_dir == Path("."):
            dirs[:] = [d for d in dirs if d in SOURCE_DIRS]
        else:
            dirs[:] = [d for d in dirs if d not in SKIP and d not in {"data", "logs"}]
        if relative_dir == Path("docs/evidence"):
            dirs[:] = []
            continue
        for directory in dirs:
            if (current / directory).is_symlink():
                raise ValueError("source_symlink_not_supported")
        for name in files:
            source = current / name
            relative = source.relative_to(root)
            if name == ".env" or name.startswith(".env.") and name != ".env.example":
                continue
            if name.endswith((".pyc", ".zip")):
                continue
            if relative_dir == Path(".") and name not in {
                "README.md",
                "CHANGELOG.md",
                "requirements.txt",
                "requirements-dev.txt",
                "pyproject.toml",
                ".gitignore",
                ".env.example",
                ".dockerignore",
                "compose.yaml",
            }:
                continue
            if source.is_symlink() or not source.resolve().is_relative_to(root):
                raise ValueError("source_escapes_repository")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


@contextmanager
def workspace(root, *, temporary_parent=None):
    """Recreate old paths only in a disposable copy of the current implementation."""
    root = Path(root).resolve()
    records = read_records(root)
    parent = Path(temporary_parent or tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="eap-evidence-", dir=parent) as folder:
        destination = Path(folder).resolve()
        if destination.parent != parent or not destination.name.startswith(
            "eap-evidence-"
        ):
            raise ValueError("invalid_temporary_directory")
        _copy_sources(root, destination)
        for name, raw in records.items():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("archive_target_escapes_workspace")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        yield destination
