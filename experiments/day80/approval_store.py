"""Local-only human approval and transactional simulated delivery. No network."""

import hashlib
import json
import re
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

RECIPIENTS = ("sales-manager-demo", "finance-demo")
REASONS = ("not_needed", "needs_revision")
MAX_EVENTS = 128
FIELDS = {
    "action",
    "recipient",
    "body",
    "note",
    "source_task_id",
    "agent_run_id",
    "source_status",
    "answer_source",
    "degraded",
    "fictional",
    "case",
}


class ApprovalError(RuntimeError):
    pass


def validate_proposal(proposal):
    if not isinstance(proposal, dict) or set(proposal) != FIELDS:
        raise ApprovalError("invalid_proposal")
    if (
        proposal["action"] != "simulate_send_sales_brief"
        or proposal["recipient"] not in RECIPIENTS
        or proposal["fictional"] is not True
        or type(proposal["degraded"]) is not bool
        or proposal["case"] not in ("monthly", "customer", "empty")
        or proposal["source_status"] not in ("completed", "no_data")
        or proposal["answer_source"]
        not in ("verified_report_template", "validated_receipt_fallback")
    ):
        raise ApprovalError("invalid_proposal")
    for key in ("source_task_id", "agent_run_id"):
        if not isinstance(proposal[key], str) or not re.fullmatch(
            r"[0-9a-f]{32}", proposal[key]
        ):
            raise ApprovalError("invalid_proposal")
    if (
        not isinstance(proposal["body"], str)
        or not 1 <= len(proposal["body"]) <= 4000
        or not isinstance(proposal["note"], str)
        or len(proposal["note"]) > 200
        or proposal["agent_run_id"] + "/T1" not in proposal["body"]
    ):
        raise ApprovalError("invalid_proposal")
    return proposal


def canonical(proposal):
    validate_proposal(proposal)
    return json.dumps(
        proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def digest(proposal):
    return hashlib.sha256(canonical(proposal).encode("utf-8")).hexdigest()


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds")


class ApprovalStore:
    def __init__(self, path, *, clock=time.time):
        self.path, self.clock = Path(path), clock

    def initialize(self):
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
                if version not in (0, 80) or (version == 0 and tables):
                    raise ApprovalError("unsupported_approval_database")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS approvals ("
                    "approval_id TEXT PRIMARY KEY, source_task_id TEXT NOT NULL, "
                    "revision INTEGER NOT NULL, parent_id TEXT, status TEXT NOT NULL, "
                    "proposal TEXT NOT NULL, digest TEXT NOT NULL, created_at INTEGER NOT NULL, "
                    "expires_at INTEGER NOT NULL, UNIQUE(source_task_id, revision))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS approval_events ("
                    "approval_id TEXT NOT NULL REFERENCES approvals(approval_id), seq INTEGER NOT NULL, "
                    "kind TEXT NOT NULL, at INTEGER NOT NULL, details TEXT NOT NULL, "
                    "PRIMARY KEY(approval_id, seq))"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS simulated_outbox ("
                    "approval_id TEXT PRIMARY KEY REFERENCES approvals(approval_id), "
                    "digest TEXT NOT NULL, proposal TEXT NOT NULL, created_at INTEGER NOT NULL)"
                )
                db.execute("PRAGMA user_version=80")
        except (sqlite3.Error, OSError):
            raise ApprovalError("approval_store_unavailable") from None

    @contextmanager
    def transaction(self, *, write=False):
        db = None
        try:
            uri = self.path.resolve().as_uri() + ("?mode=rw" if write else "?mode=ro")
            db = sqlite3.connect(uri, uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            if db.execute("PRAGMA user_version").fetchone()[0] != 80:
                raise ApprovalError("unsupported_approval_database")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except sqlite3.Error:
            raise ApprovalError("approval_store_unavailable") from None
        finally:
            if db is not None:
                db.close()  # Uncommitted writes roll back, including log failures.

    def event(self, db, approval_id, kind, details, now):
        seq = db.execute(
            "SELECT COUNT(*)+1 FROM approval_events WHERE approval_id=?", (approval_id,)
        ).fetchone()[0]
        if seq > MAX_EVENTS:
            raise ApprovalError("approval_event_limit")
        db.execute(
            "INSERT INTO approval_events VALUES (?, ?, ?, ?, ?)",
            (approval_id, seq, kind, now, json.dumps(details, ensure_ascii=False)),
        )

    def row(self, db, approval_id):
        row = db.execute(
            "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
        ).fetchone()
        if row is None:
            raise ApprovalError("approval_not_found")
        try:
            proposal = json.loads(row["proposal"])
            if (
                digest(proposal) != row["digest"]
                or proposal["source_task_id"] != row["source_task_id"]
            ):
                raise ApprovalError("proposal_integrity_failed")
        except (ValueError, TypeError, KeyError):
            raise ApprovalError("proposal_integrity_failed") from None
        return dict(row), proposal

    def insert(self, db, proposal, now, ttl, *, revision=1, parent=None):
        approval_id = uuid.uuid4().hex
        db.execute(
            "INSERT INTO approvals VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
            (
                approval_id,
                proposal["source_task_id"],
                revision,
                parent,
                canonical(proposal),
                digest(proposal),
                now,
                now + ttl,
            ),
        )
        self.event(
            db,
            approval_id,
            "approval_requested",
            {
                "digest": digest(proposal),
                "revision": revision,
                "parent_id": parent,
                "mode": "local_simulation_only",
            },
            now,
        )
        return approval_id

    @staticmethod
    def validate_ttl(ttl):
        if type(ttl) is not int or not 1 <= ttl <= 86400:
            raise ApprovalError("invalid_ttl")

    def create(self, proposal, *, ttl=1800):
        validate_proposal(proposal)
        self.validate_ttl(ttl)
        self.initialize()
        with self.transaction(write=True) as db:
            now = int(self.clock())
            existing = db.execute(
                "SELECT approval_id FROM approvals WHERE source_task_id=? "
                "AND revision=1",
                (proposal["source_task_id"],),
            ).fetchone()
            if existing:
                row, _ = self.row(db, existing[0])
                if row["digest"] != digest(proposal):
                    raise ApprovalError("source_task_conflict")
                return self.view(db, existing[0], now)
            approval_id = self.insert(db, proposal, now, ttl)
            return self.view(db, approval_id, now)

    def guard(self, db, row, expected, now):
        if expected != row["digest"]:
            self.event(
                db,
                row["approval_id"],
                "decision_blocked",
                {"reason": "digest_mismatch"},
                now,
            )
            return "digest_mismatch"
        if row["status"] != "pending":
            return "not_pending"
        if now >= row["expires_at"]:
            db.execute(
                "UPDATE approvals SET status='expired' WHERE approval_id=?",
                (row["approval_id"],),
            )
            self.event(db, row["approval_id"], "approval_expired", {}, now)
            return "expired"
        return None

    def decide(self, approval_id, expected, decision, *, reason="not_needed"):
        if decision not in ("approve", "reject") or reason not in REASONS:
            raise ApprovalError("invalid_decision")
        with self.transaction(write=True) as db:
            now = int(self.clock())
            row, proposal = self.row(db, approval_id)
            blocked = self.guard(db, row, expected, now)
            if blocked:
                result = self.view(db, approval_id, now)
                result["decision_result"] = (
                    "already_executed"
                    if blocked == "not_pending"
                    and row["status"] == "executed"
                    and decision == "approve"
                    else blocked
                )
                return result
            if decision == "reject":
                db.execute(
                    "UPDATE approvals SET status='rejected' WHERE approval_id=?",
                    (approval_id,),
                )
                self.event(
                    db,
                    approval_id,
                    "human_rejected",
                    {"reason": reason, "actor": "local_cli_user"},
                    now,
                )
            else:
                # This transaction IS the entire simulated effect. It is not an
                # exactly-once guarantee for any external messaging service.
                self.event(
                    db,
                    approval_id,
                    "human_approved",
                    {
                        "digest": expected,
                        "actor": "local_cli_user",
                        "identity_verified": False,
                    },
                    now,
                )
                db.execute(
                    "INSERT INTO simulated_outbox VALUES (?, ?, ?, ?)",
                    (approval_id, expected, canonical(proposal), now),
                )
                db.execute(
                    "UPDATE approvals SET status='executed' WHERE approval_id=?",
                    (approval_id,),
                )
                self.event(
                    db,
                    approval_id,
                    "simulation_executed",
                    {"external_send": False},
                    now,
                )
            result = self.view(db, approval_id, now)
            result["decision_result"] = (
                "executed" if decision == "approve" else "rejected"
            )
            return result

    def revise(self, approval_id, expected, *, recipient=None, note=None, ttl=1800):
        self.validate_ttl(ttl)
        with self.transaction(write=True) as db:
            now = int(self.clock())
            row, proposal = self.row(db, approval_id)
            blocked = self.guard(db, row, expected, now)
            if blocked:
                result = self.view(db, approval_id, now)
                result["decision_result"] = blocked
                return result
            if recipient is not None:
                proposal["recipient"] = recipient
            if note is not None:
                proposal["note"] = note
            validate_proposal(proposal)
            if digest(proposal) == row["digest"]:
                raise ApprovalError("no_content_change")
            new_id = self.insert(
                db, proposal, now, ttl, revision=row["revision"] + 1, parent=approval_id
            )
            db.execute(
                "UPDATE approvals SET status='superseded' WHERE approval_id=?",
                (approval_id,),
            )
            self.event(
                db, approval_id, "approval_superseded", {"replacement_id": new_id}, now
            )
            result = self.view(db, new_id, now)
            result["decision_result"] = "revised"
            return result

    def view(self, db, approval_id, now):
        row, proposal = self.row(db, approval_id)
        events = [
            dict(item)
            for item in db.execute(
                "SELECT seq, kind, at, details FROM approval_events WHERE approval_id=? ORDER BY seq LIMIT ?",
                (approval_id, MAX_EVENTS + 1),
            )
        ]
        if len(events) > MAX_EVENTS:
            raise ApprovalError("invalid_approval_log")
        for seq, event in enumerate(events, 1):
            if event["seq"] != seq:
                raise ApprovalError("invalid_approval_log")
            event["at"] = iso(event["at"])
            event["details"] = json.loads(event["details"])
        outbox = db.execute(
            "SELECT digest, proposal FROM simulated_outbox WHERE approval_id=?",
            (approval_id,),
        ).fetchone()
        if (row["status"] == "executed") != (outbox is not None):
            raise ApprovalError("invalid_execution_state")
        if outbox is not None and (
            outbox["digest"] != row["digest"] or outbox["proposal"] != row["proposal"]
        ):
            raise ApprovalError("simulation_integrity_failed")
        return {
            "approval_id": approval_id,
            "revision": row["revision"],
            "parent_id": row["parent_id"],
            "status": row["status"],
            "effective_status": "expired"
            if row["status"] == "pending" and now >= row["expires_at"]
            else row["status"],
            "digest": row["digest"],
            "proposal": proposal,
            "created_at": iso(row["created_at"]),
            "expires_at": iso(row["expires_at"]),
            "events": events,
            "simulation_count": int(outbox is not None),
            "external_send": False,
        }

    def show(self, approval_id):
        with self.transaction() as db:
            return self.view(db, approval_id, int(self.clock()))

    def list(self):
        with self.transaction() as db:
            now = int(self.clock())
            rows = db.execute(
                "SELECT approval_id, source_task_id, revision, status, expires_at FROM approvals "
                "ORDER BY created_at DESC, approval_id DESC LIMIT 100"
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["effective_status"] = (
                    "expired"
                    if item["status"] == "pending" and now >= item["expires_at"]
                    else item["status"]
                )
                item["expires_at"] = iso(item["expires_at"])
                result.append(item)
            return {"read_only": True, "limit": 100, "approvals": result}
