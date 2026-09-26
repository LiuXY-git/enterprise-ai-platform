"""Durable per-task event log. Reading never resumes or executes a task."""

import json
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

TERMINAL = {"completed", "no_data", "needs_clarification", "rejected", "failed"}
KINDS = {
    "user_request",
    "discovery_started",
    "discovery_result",
    "model_started",
    "agent_decision",
    "tool_call",
    "tool_result",
    "tool_feedback",
    "stage_error",
    "final_answer",
}
MAX_EVENTS = 64
MAX_PAYLOAD = 16384


class JournalError(RuntimeError):
    """Do not continue an operation whose preceding event could not be saved."""


def utc_now():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def encode(payload):
    if not isinstance(payload, dict):
        raise JournalError("invalid_payload")
    try:
        text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise JournalError("invalid_payload") from None
    if len(text.encode("utf-8")) > MAX_PAYLOAD:
        raise JournalError("payload_too_large")
    return text


class TaskLog:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                tables = {
                    r[0]
                    for r in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if (version == 0 and tables) or version not in (0, 1):
                    raise JournalError("unsupported_log_database")
                db.execute("PRAGMA synchronous=FULL")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS tasks ("
                    "task_id TEXT PRIMARY KEY, case_name TEXT NOT NULL, "
                    "mode TEXT NOT NULL, status TEXT NOT NULL, "
                    "created_at TEXT NOT NULL, finished_at TEXT)"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS events ("
                    "task_id TEXT NOT NULL REFERENCES tasks(task_id), "
                    "seq INTEGER NOT NULL, kind TEXT NOT NULL, "
                    "at TEXT NOT NULL, elapsed_ms INTEGER NOT NULL, "
                    "payload TEXT NOT NULL, PRIMARY KEY(task_id, seq))"
                )
                db.execute("PRAGMA user_version=1")
        except (OSError, sqlite3.Error):
            raise JournalError("log_unavailable") from None

    def start(self, case, mode, goal):
        task_id = uuid.uuid4().hex
        payload = encode({"case": case, "goal": goal, "fictional": True})
        now = utc_now()
        try:
            with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
                db.execute(
                    "INSERT INTO tasks VALUES (?, ?, ?, 'running', ?, NULL)",
                    (task_id, case, mode, now),
                )
                db.execute(
                    "INSERT INTO events VALUES (?, 1, 'user_request', ?, 0, ?)",
                    (task_id, now, payload),
                )
        except sqlite3.Error:
            raise JournalError("log_write_failed") from None
        return RunLog(self, task_id)


class RunLog:
    def __init__(self, store, task_id):
        self.store, self.task_id = store, task_id
        self.started = time.monotonic()
        self.broken = False

    def emit(self, kind, payload, *, status=None):
        if self.broken:
            raise JournalError("log_already_failed")
        try:
            if kind not in KINDS or kind == "user_request":
                raise JournalError("invalid_event_kind")
            if (kind == "final_answer") != (status in TERMINAL):
                raise JournalError("invalid_terminal_event")
            if status is not None and status not in TERMINAL:
                raise JournalError("invalid_status")
            text = encode(payload)
            with closing(sqlite3.connect(self.store.path, timeout=5)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT status FROM tasks WHERE task_id=?", (self.task_id,)
                ).fetchone()
                if row != ("running",):
                    raise JournalError("task_not_running")
                seq = db.execute(
                    "SELECT COALESCE(MAX(seq), 0)+1 FROM events WHERE task_id=?",
                    (self.task_id,),
                ).fetchone()[0]
                if seq > MAX_EVENTS:
                    raise JournalError("event_limit")
                now = utc_now()
                elapsed = max(0, int((time.monotonic() - self.started) * 1000))
                db.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                    (self.task_id, seq, kind, now, elapsed, text),
                )
                if status is not None:
                    db.execute(
                        "UPDATE tasks SET status=?, finished_at=? WHERE task_id=?",
                        (status, now, self.task_id),
                    )
        except (JournalError, sqlite3.Error):
            self.broken = True
            raise JournalError("log_write_failed") from None


def read_log(path, task_id=None):
    """Bounded read-only snapshot; a running record may be active or interrupted."""
    try:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            if db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise JournalError("unsupported_log_database")
            if task_id is None:
                rows = db.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC, "
                    "task_id DESC LIMIT 100"
                ).fetchall()
                return {
                    "read_only": True,
                    "limit": 100,
                    "tasks": [dict(row) for row in rows],
                }
            row = db.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise JournalError("task_not_found")
            rows = db.execute(
                "SELECT seq, kind, at, elapsed_ms, payload FROM events "
                "WHERE task_id=? ORDER BY seq LIMIT ?",
                (task_id, MAX_EVENTS + 1),
            ).fetchall()
            events = []
            if len(rows) > MAX_EVENTS:
                raise JournalError("invalid_log")
            for index, item in enumerate(rows, 1):
                item = dict(item)
                if item["seq"] != index or item["kind"] not in KINDS:
                    raise JournalError("invalid_log")
                if len(item["payload"].encode("utf-8")) > MAX_PAYLOAD:
                    raise JournalError("invalid_log")
                item["payload"] = json.loads(item["payload"])
                events.append(item)
            terminal = row["status"] in TERMINAL
            if (
                not events
                or events[0]["kind"] != "user_request"
                or terminal != (events[-1]["kind"] == "final_answer")
            ):
                raise JournalError("invalid_log")
            return {
                "read_only": True,
                "task": dict(row),
                "events": events,
                "terminal_recorded": terminal,
                "notice": "recorded_terminal" if terminal else "running_or_interrupted",
            }
    except (sqlite3.Error, OSError, ValueError, TypeError):
        raise JournalError("log_read_failed") from None
