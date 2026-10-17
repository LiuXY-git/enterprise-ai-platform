"""Reuse the existing approval transaction, with atomic HTTP idempotency receipts."""

import hashlib
import json
import re
from contextlib import contextmanager

from experiments.day80.approval_store import ApprovalError, ApprovalStore, iso

from .store import encoded


class DecisionConflict(Exception):
    pass


class WebApprovalStore(ApprovalStore):
    # One instance per request, never shared between threads. Nested transactions
    # let the original decide() and the HTTP receipt commit/rollback together.
    active = None

    @contextmanager
    def transaction(self, *, write=False):
        if self.active is not None:
            yield self.active
        else:
            with super().transaction(write=write) as db:
                yield db

    def decide_once(self, approval_id, request, key):
        fingerprint = hashlib.sha256(encoded(request).encode("utf-8")).hexdigest()
        with super().transaction(write=True) as db:
            self.active = db
            try:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS console_decisions "
                    "(request_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL)"
                )
                old = db.execute(
                    "SELECT * FROM console_decisions WHERE request_key=?", (key,)
                ).fetchone()
                if old:
                    if old["fingerprint"] != fingerprint:
                        raise DecisionConflict()
                    return {
                        **self.view(db, approval_id, int(self.clock())),
                        "decision_result": old["result"],
                        "reused": True,
                    }
                row, _ = self.row(db, approval_id)
                if row["revision"] != request["revision"]:
                    result = {
                        **self.view(db, approval_id, int(self.clock())),
                        "decision_result": "revision_mismatch",
                    }
                else:
                    result = super().decide(
                        approval_id,
                        request["digest"],
                        request["decision"],
                        reason=request["reason"],
                    )
                db.execute(
                    "INSERT INTO console_decisions VALUES (?,?,?)",
                    (key, fingerprint, result["decision_result"]),
                )
                return {**result, "reused": False}
            finally:
                self.active = None

    def display(self, approval_id, job):
        with self.transaction() as db:
            result = self.view(db, approval_id, int(self.clock()))
            sources = job["source_ids"]
            if (
                result["proposal"]["source_task_id"] != sources["task_id"]
                or result["proposal"]["agent_run_id"] != sources["run_id"]
                or result["proposal"]["body"] != job["result"]["answer"]
            ):
                raise ApprovalError("job_proposal_mismatch")
            messages = []
            for row in db.execute(
                "SELECT * FROM simulated_outbox WHERE approval_id=?", (approval_id,)
            ):
                proposal = json.loads(row["proposal"])
                messages.append(
                    {
                        "approval_id": approval_id,
                        "digest": row["digest"],
                        "recipient": proposal["recipient"],
                        "body": proposal["body"],
                        "created_at": iso(row["created_at"]),
                        "external_send": False,
                    }
                )
            return {
                **result,
                "job_id": job["job_id"],
                "mode": "fixture",
                "simulated_messages": messages,
            }


def for_job(config, job):
    if not re.fullmatch(r"[0-9a-f]{32}", job["job_id"]):
        raise ApprovalError("invalid_job_id")
    path = config.data_dir / "runs" / job["job_id"] / "approvals.sqlite"
    if not path.is_file():
        raise ApprovalError("approval_store_unavailable")
    return WebApprovalStore(path)
