"""SQLite queue with atomic idempotency, a worker lease and fenced writes."""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class QueueConflict(Exception):
    pass


class QueueFull(Exception):
    pass


class JobNotFound(Exception):
    pass


class LeaseLost(Exception):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat(timespec="milliseconds")


ERROR_MESSAGES = {
    "configuration_missing": "n8n connection is not configured. No request was sent.",
    "workflow_outcome_unknown": "External outcome is unknown. Check n8n using the event ID; do not blindly replay.",
    "worker_interrupted": "Worker stopped; this task will not be replayed.",
    "worker_lease_expired": "Worker heartbeat expired; inspect before retrying.",
    "task_timeout": "Task exceeded the server execution limit.",
    "task_failed": "Local task failed; inspect server logs.",
    "invalid_task_result": "Local task did not return a valid result.",
}


def error(code):
    return encoded({"code": code, "message": ERROR_MESSAGES[code]})


class QueueStore:
    def __init__(self, path: Path, *, queue_limit=32, clock=time.time):
        self.path = Path(path)
        self.queue_limit = queue_limit
        self.clock = clock

    @contextmanager
    def connection(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS console_jobs (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    request_key TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    kind TEXT NOT NULL, mode TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                        ('queued','running','succeeded','failed','interrupted')),
                    stage TEXT NOT NULL,
                    owner TEXT,
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    started_at TEXT, finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS console_jobs_status
                    ON console_jobs(status, seq);
                CREATE TABLE IF NOT EXISTS console_approvals (
                    approval_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE REFERENCES console_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS console_worker (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    owner TEXT, heartbeat REAL NOT NULL, expires REAL NOT NULL
                );
            """)

            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(console_jobs)")}
            if "progress_json" not in columns:
                db.execute(
                    "ALTER TABLE console_jobs ADD COLUMN progress_json TEXT NOT NULL DEFAULT '{}'"
                )

            db.commit()

    def progress(self, job_id, owner, stage, value):
        with self.connection(write=True) as db:
            self._check_lease(db, owner, self.clock())
            if (
                db.execute(
                    "UPDATE console_jobs SET stage=?,progress_json=?,updated_at=? WHERE job_id=? AND owner=? AND status='running'",
                    (stage, encoded(value), stamp(self.clock()), job_id, owner),
                ).rowcount
                != 1
            ):
                raise LeaseLost()

    @staticmethod
    def view(row):
        if row is None:
            raise JobNotFound()
        return {
            **{
                key: row[key]
                for key in (
                    "job_id",
                    "kind",
                    "mode",
                    "status",
                    "stage",
                    "created_at",
                    "updated_at",
                    "started_at",
                    "finished_at",
                )
            },
            "progress": json.loads(row["progress_json"]),
            "input": json.loads(row["input_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
            "source_ids": json.loads(row["result_json"]).get("source_ids", {})
            if row["result_json"]
            else {},
        }

    def submit(self, request, key):
        fingerprint = hashlib.sha256(encoded(request).encode("utf-8")).hexdigest()
        with self.connection(write=True) as db:
            old = db.execute(
                "SELECT * FROM console_jobs WHERE request_key=?", (key,)
            ).fetchone()
            if old:
                if old["request_hash"] != fingerprint:
                    raise QueueConflict()
                return self.view(old), True
            count = db.execute(
                "SELECT COUNT(*) FROM console_jobs WHERE status='queued'"
            ).fetchone()[0]
            if count >= self.queue_limit:
                raise QueueFull()
            job_id, now = uuid4().hex, stamp(self.clock())
            db.execute(
                """INSERT INTO console_jobs
                (job_id,request_key,request_hash,kind,mode,input_json,status,stage,
                 created_at,updated_at)
                VALUES (?,?,?,?,?,?,'queued','queued',?,?)""",
                (
                    job_id,
                    key,
                    fingerprint,
                    request["kind"],
                    request["mode"],
                    encoded(request["input"]),
                    now,
                    now,
                ),
            )
            return self.view(
                db.execute(
                    "SELECT * FROM console_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            ), False

    def get(self, job_id):
        with self.connection() as db:
            return self.view(
                db.execute(
                    "SELECT * FROM console_jobs WHERE job_id=?", (job_id,)
                ).fetchone()
            )

    def approval_job(self, approval_id):
        with self.connection() as db:
            return self.view(
                db.execute(
                    "SELECT j.* FROM console_jobs j JOIN console_approvals a ON j.job_id=a.job_id "
                    "WHERE a.approval_id=? AND j.status='succeeded' AND j.kind='agent'",
                    (approval_id,),
                ).fetchone()
            )

    def list(self, *, limit=20, offset=0, status=None, kind=None):
        where, args = (" WHERE status=?", [status]) if status else ("", [])
        if kind:
            where += (" AND " if where else " WHERE ") + "kind=?"
            args.append(kind)
        with self.connection() as db:
            db.execute("BEGIN")
            total = db.execute(
                "SELECT COUNT(*) FROM console_jobs" + where, args
            ).fetchone()[0]
            rows = db.execute(
                "SELECT * FROM console_jobs"
                + where
                + " ORDER BY seq DESC LIMIT ? OFFSET ?",
                [*args, limit, offset],
            ).fetchall()
            return {
                "jobs": [self.view(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def acquire(self, owner, lease_seconds):
        with self.connection(write=True) as db:
            now = self.clock()
            current = db.execute(
                "SELECT * FROM console_worker WHERE singleton=1"
            ).fetchone()
            if current and current["owner"] and current["expires"] > now:
                return False
            db.execute(
                """UPDATE console_jobs SET status='interrupted', stage='interrupted',
                finished_at=?, updated_at=?, error_json=? WHERE status='running'""",
                (stamp(now), stamp(now), error("worker_lease_expired")),
            )
            db.execute(
                "INSERT OR REPLACE INTO console_worker VALUES (1,?,?,?)",
                (owner, now, now + lease_seconds),
            )
            return True

    def _check_lease(self, db, owner, now):
        row = db.execute("SELECT * FROM console_worker WHERE singleton=1").fetchone()
        if not row or row["owner"] != owner or row["expires"] <= now:
            raise LeaseLost()

    def heartbeat(self, owner, lease_seconds):
        with self.connection(write=True) as db:
            now = self.clock()
            self._check_lease(db, owner, now)
            db.execute(
                "UPDATE console_worker SET heartbeat=?, expires=? WHERE singleton=1",
                (now, now + lease_seconds),
            )

    def claim(self, owner):
        with self.connection(write=True) as db:
            now = self.clock()
            self._check_lease(db, owner, now)
            if db.execute(
                "SELECT 1 FROM console_jobs WHERE status='running'"
            ).fetchone():
                return None
            row = db.execute(
                "SELECT * FROM console_jobs WHERE status='queued' ORDER BY seq LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                """UPDATE console_jobs SET status='running',stage='executing',owner=?,
                started_at=?,updated_at=? WHERE job_id=? AND status='queued'""",
                (owner, stamp(now), stamp(now), row["job_id"]),
            )
            return self.view(
                db.execute(
                    "SELECT * FROM console_jobs WHERE job_id=?", (row["job_id"],)
                ).fetchone()
            )

    def finish(self, job_id, owner, *, result=None, error_code=None, interrupted=False):
        with self.connection(write=True) as db:
            now = self.clock()
            self._check_lease(db, owner, now)
            state = (
                "interrupted"
                if interrupted
                else "failed"
                if error_code
                else "succeeded"
            )
            changed = db.execute(
                """UPDATE console_jobs SET status=?,stage=?,result_json=?,error_json=?,
                updated_at=?,finished_at=? WHERE job_id=? AND owner=? AND status='running'""",
                (
                    state,
                    state,
                    encoded(result) if result is not None else None,
                    error(error_code) if error_code else None,
                    stamp(now),
                    stamp(now),
                    job_id,
                    owner,
                ),
            ).rowcount
            if changed != 1:
                raise LeaseLost()
            approval_id = (result or {}).get("source_ids", {}).get("approval_id")
            if approval_id:
                db.execute(
                    "INSERT INTO console_approvals VALUES (?,?)", (approval_id, job_id)
                )

    def release(self, owner):
        with self.connection(write=True) as db:
            now = self.clock()
            row = db.execute(
                "SELECT owner FROM console_worker WHERE singleton=1"
            ).fetchone()
            if row and row["owner"] == owner:
                db.execute(
                    """UPDATE console_jobs SET status='interrupted',stage='interrupted',
                    updated_at=?,finished_at=?,error_json=? WHERE owner=? AND status='running'""",
                    (stamp(now), stamp(now), error("worker_interrupted"), owner),
                )
                db.execute(
                    "UPDATE console_worker SET owner=NULL,expires=? WHERE singleton=1",
                    (now,),
                )

    def worker_status(self):
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM console_worker WHERE singleton=1"
            ).fetchone()
        if not row:
            return {"status": "missing", "heartbeat_at": None, "lease_expires_at": None}
        state = (
            "stopped"
            if row["owner"] is None
            else "healthy"
            if row["expires"] > self.clock()
            else "stale"
        )
        return {
            "status": state,
            "heartbeat_at": stamp(row["heartbeat"]),
            "lease_expires_at": stamp(row["expires"]),
        }
