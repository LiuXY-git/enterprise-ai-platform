"""Thread-scoped SQLite memory with durable request IDs and explicit clearing."""

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing, contextmanager
from pathlib import Path

APP_ID = 7501
MAX_TURNS = 200
HISTORY_PAIRS = 4
DEPARTMENTS = ("销售", "财务", "运营")
SCHEMA = """
CREATE TABLE sessions (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, generation INTEGER NOT NULL DEFAULT 0,
 department TEXT, source_request TEXT
) STRICT;
CREATE TABLE turns (
 session_id TEXT NOT NULL REFERENCES sessions(id), request_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL, generation INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','completed','failed','cleared')),
 user_text TEXT, assistant_text TEXT, result TEXT,
 PRIMARY KEY(session_id,request_id)
) STRICT;
CREATE UNIQUE INDEX one_pending ON turns(session_id) WHERE status='pending';
PRAGMA application_id=7501;
PRAGMA user_version=1;
"""


class MemoryError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise MemoryError("invalid_identifier")
    return value


def intent(text):
    """Explicit teaching vocabulary; never extract facts from model guesses."""
    if not isinstance(text, str) or len(text) > 100:
        raise MemoryError("unsupported_message")
    normalized = text.strip().rstrip("。！？!? ")
    for department in DEPARTMENTS:
        if normalized in (f"我负责{department}部门", f"改为{department}部门"):
            return "department", department
    if normalized == "给我生成日报模板":
        return "template", None
    if normalized == "给我生成日报":
        return "report", None
    raise MemoryError("unsupported_message")


class MemoryStore:
    def __init__(self, path):
        self.path = Path(path).resolve()

    def initialize(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("xb"):
                pass
        except FileExistsError:
            raise MemoryError("database_already_exists") from None
        except OSError:
            raise MemoryError("storage_unavailable") from None
        try:
            with closing(sqlite3.connect(self.path)) as connection:
                connection.executescript(SCHEMA)
        except sqlite3.Error:
            raise MemoryError("storage_initialization_failed") from None
        return {"status": "initialized"}

    @contextmanager
    def transaction(self):
        try:
            with closing(
                sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=2)
            ) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                if (
                    connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                    or connection.execute("PRAGMA user_version").fetchone()[0] != 1
                ):
                    raise MemoryError("wrong_memory_database")
                connection.execute("BEGIN IMMEDIATE")
                try:
                    yield connection
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
        except sqlite3.Error:
            raise MemoryError("storage_unavailable") from None

    def owned(self, connection, owner, session):
        identifier(owner)
        identifier(session)
        row = connection.execute(
            "SELECT * FROM sessions WHERE id=? AND owner=?", (session, owner)
        ).fetchone()
        if row is None:
            raise MemoryError("session_unavailable")
        return row

    def create(self, owner):
        identifier(owner)
        session = uuid.uuid4().hex
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO sessions(id,owner) VALUES(?,?)", (session, owner)
            )
        return {"status": "created", "session_id": session, "owner": owner}

    def context(self, connection, row):
        history = connection.execute(
            "SELECT request_id,user_text,assistant_text FROM turns WHERE session_id=? AND status='completed' ORDER BY rowid DESC LIMIT ?",
            (row["id"], HISTORY_PAIRS),
        ).fetchall()
        count = connection.execute(
            "SELECT count(*) FROM turns WHERE session_id=? AND status='completed'",
            (row["id"],),
        ).fetchone()[0]
        messages = []
        for item in reversed(history):
            messages.extend(
                [
                    {"role": "user", "content": item["user_text"]},
                    {"role": "assistant", "content": item["assistant_text"]},
                ]
            )
        return {
            "department": row["department"],
            "source_request_id": row["source_request"],
            "history": messages,
            "included_pairs": len(history),
            "omitted_pairs": count - len(history),
            "history_pair_limit": HISTORY_PAIRS,
        }

    def begin(self, owner, session, request, text, mode):
        identifier(request)
        intent(text)
        if mode not in ("fixture", "live"):
            raise MemoryError("invalid_mode")
        fingerprint = hashlib.sha256(
            json.dumps([text, mode], ensure_ascii=False).encode()
        ).hexdigest()
        with self.transaction() as connection:
            row = self.owned(connection, owner, session)
            previous = connection.execute(
                "SELECT * FROM turns WHERE session_id=? AND request_id=?",
                (session, request),
            ).fetchone()
            if previous is not None:
                if previous["fingerprint"] != fingerprint:
                    raise MemoryError("request_id_conflict")
                if previous["status"] in ("pending", "cleared"):
                    return {
                        "replay": {
                            "status": previous["status"],
                            "request_id": request,
                            "reason": "request_not_reexecuted",
                            "answer": None,
                        }
                    }
                return {"replay": json.loads(previous["result"])}
            if connection.execute(
                "SELECT 1 FROM turns WHERE session_id=? AND status='pending'",
                (session,),
            ).fetchone():
                raise MemoryError("session_busy")
            if (
                connection.execute(
                    "SELECT count(*) FROM turns WHERE session_id=?", (session,)
                ).fetchone()[0]
                >= MAX_TURNS
            ):
                raise MemoryError("session_capacity_reached")
            context = self.context(connection, row)
            connection.execute(
                "INSERT INTO turns(session_id,request_id,fingerprint,generation,status,user_text) VALUES(?,?,?,?,'pending',?)",
                (session, request, fingerprint, row["generation"], text),
            )
            return {"generation": row["generation"], "context": context}

    def finish(self, owner, session, request, generation, result, department=None):
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded) > 16000 or result.get("status") not in (
            "completed",
            "needs_clarification",
            "failed",
        ):
            raise MemoryError("invalid_turn_result")
        if department is not None and department not in DEPARTMENTS:
            raise MemoryError("invalid_department")
        with self.transaction() as connection:
            row = self.owned(connection, owner, session)
            turn = connection.execute(
                "SELECT * FROM turns WHERE session_id=? AND request_id=?",
                (session, request),
            ).fetchone()
            if (
                not turn
                or turn["status"] != "pending"
                or row["generation"] != generation
                or turn["generation"] != generation
            ):
                raise MemoryError("stale_turn")
            status = "failed" if result["status"] == "failed" else "completed"
            answer = result.get("answer")
            if status == "completed" and (
                not isinstance(answer, str) or len(answer) > 2000
            ):
                raise MemoryError("invalid_turn_result")
            if department is not None:
                if status != "completed":
                    raise MemoryError("invalid_turn_result")
                connection.execute(
                    "UPDATE sessions SET department=?,source_request=? WHERE id=?",
                    (department, request, session),
                )
            connection.execute(
                "UPDATE turns SET status=?,assistant_text=?,result=? WHERE session_id=? AND request_id=?",
                (status, answer, encoded, session, request),
            )

    def inspect(self, owner, session):
        with self.transaction() as connection:
            row = self.owned(connection, owner, session)
            turns = connection.execute(
                "SELECT request_id,status,user_text,assistant_text FROM turns WHERE session_id=? AND status!='cleared' ORDER BY rowid",
                (session,),
            ).fetchall()
            return {
                "status": "available",
                "session_id": session,
                "generation": row["generation"],
                "context": self.context(connection, row),
                "turns": [dict(t) for t in turns],
            }

    def clear(self, owner, session):
        with self.transaction() as connection:
            self.owned(connection, owner, session)
            connection.execute(
                "UPDATE sessions SET generation=generation+1,department=NULL,source_request=NULL WHERE id=?",
                (session,),
            )
            connection.execute(
                "UPDATE turns SET status='cleared',user_text=NULL,assistant_text=NULL,result=NULL WHERE session_id=?",
                (session,),
            )
        return {
            "status": "cleared",
            "session_id": session,
            "scope": "active_context_and_saved_turn_payloads",
            "request_id_tombstones_retained": True,
            "forensic_erasure": False,
        }

    def cancel(self, owner, session, request):
        identifier(request)
        with self.transaction() as connection:
            self.owned(connection, owner, session)
            result = {
                "status": "failed",
                "reason": "cancelled_pending_request",
                "request_id": request,
                "answer": None,
                "prior_model_execution": "unknown",
            }
            cursor = connection.execute(
                "UPDATE turns SET status='failed',result=? WHERE session_id=? AND request_id=? AND status='pending'",
                (json.dumps(result), session, request),
            )
            if cursor.rowcount != 1:
                raise MemoryError("no_pending_request")
        return result
