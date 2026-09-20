"""Local SQLite checkpoints, stable task IDs and serialized resumptions."""

import json
import sqlite3
import sys
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from filelock import FileLock, Timeout
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from langsmith import tracing_context
from progress_graph import build_graph

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day59"))
from plan_schema import parse_plan  # noqa: E402

GRAPH_VERSION = 1


class StoreError(Exception):
    pass


def normalize_plan(value: dict) -> dict:
    if isinstance(value, dict) and value.get("artifact_type") == "task_planning_result":
        if (
            not isinstance(value.get("state"), dict)
            or value["state"].get("status") != "planned"
        ):
            raise StoreError("plan_not_ready")
        value = value["state"].get("plan")
    try:
        plan = parse_plan(json.dumps(value, ensure_ascii=False))
    except (ValueError, TypeError, RecursionError):
        raise StoreError("invalid_plan") from None
    if plan.decision != "plan":
        raise StoreError("plan_not_ready")
    return plan.model_dump()


def read_plan(path: Path | None) -> dict:
    if path is None:
        path = ROOT / "experiments/day59/mock-responses.json"
        return normalize_plan(json.loads(path.read_text(encoding="utf-8"))["normal"])
    try:
        with path.open("r", encoding="utf-8-sig") as source:
            raw = source.read(65537)
        if len(raw) > 65536:
            raise StoreError("plan_file_too_large")
        return normalize_plan(json.loads(raw))
    except (OSError, ValueError, TypeError, RecursionError):
        raise StoreError("invalid_plan_file") from None


class TaskStore:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def database_path(self, task_id: str) -> Path:
        try:
            if str(UUID(task_id)) != task_id:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise StoreError("invalid_task_id") from None
        path = (self.directory / f"{task_id}.sqlite").resolve()
        if not path.is_relative_to(self.directory):
            raise StoreError("invalid_task_path")
        return path

    @contextmanager
    def _connection(self, task_id: str):
        path = self.database_path(task_id)
        if not path.is_file():
            raise StoreError("task_not_found")
        lock = FileLock(str(path) + ".lock", timeout=0)
        try:
            with (
                lock,
                closing(
                    sqlite3.connect(
                        path.as_uri() + "?mode=rw", uri=True, check_same_thread=False
                    )
                ) as conn,
            ):
                conn.execute("PRAGMA synchronous=FULL")
                yield conn
        except Timeout:
            raise StoreError("task_busy") from None
        except sqlite3.Error:
            raise StoreError("invalid_task_database") from None

    @staticmethod
    def _metadata(conn, task_id):
        row = conn.execute(
            "SELECT task_id, graph_version, created_at, plan_json FROM task_metadata"
        ).fetchone()
        if not row or row[0] != task_id or row[1] != GRAPH_VERSION:
            raise StoreError("incompatible_task")
        try:
            plan = normalize_plan(json.loads(row[3]))
        except (ValueError, TypeError, RecursionError):
            raise StoreError("invalid_task_database") from None
        return {
            "task_id": row[0],
            "graph_version": row[1],
            "created_at": row[2],
            "plan": plan,
        }

    @staticmethod
    def _seed(meta):
        return {
            "task_id": meta["task_id"],
            "plan": meta["plan"],
            "cursor": 0,
            "status": "planned",
            "simulated_steps": [],
            "trace": [],
        }

    @staticmethod
    def _graph(conn):
        return build_graph(
            SqliteSaver(conn, serde=JsonPlusSerializer(pickle_fallback=False))
        )

    @staticmethod
    def _config(task_id):
        return {"configurable": {"thread_id": task_id}, "recursion_limit": 20}

    @staticmethod
    def _view(snapshot, meta):
        state = snapshot.values
        interrupted = any(task.interrupts for task in snapshot.tasks)
        if not state:
            phase = "initializing"
            state = TaskStore._seed(meta)
        elif interrupted:
            phase = "paused"
        elif snapshot.next:
            phase = "recoverable"
        else:
            phase = "finished"
        # Checkpoint state is versioned and must agree with immutable task metadata.
        expected = [step["id"] for step in meta["plan"]["steps"]]
        cursor = state.get("cursor")
        if (
            state.get("task_id") != meta["task_id"]
            or state.get("plan") != meta["plan"]
            or type(cursor) is not int
            or not 0 <= cursor <= len(expected)
            or state.get("simulated_steps") != expected[:cursor]
        ):
            raise StoreError("inconsistent_checkpoint")
        checkpoint_id = (
            (snapshot.config or {}).get("configurable", {}).get("checkpoint_id")
        )
        return {
            "task_id": meta["task_id"],
            "thread_id": meta["task_id"],
            "checkpoint_id": checkpoint_id,
            "graph_version": GRAPH_VERSION,
            "created_at": meta["created_at"],
            "phase": phase,
            "status": state["status"],
            "next_nodes": list(snapshot.next),
            "progress": {"simulated": cursor, "total": len(expected)},
            "steps": [
                {"id": step, "status": "simulated" if index < cursor else "pending"}
                for index, step in enumerate(expected)
            ],
            "plan": meta["plan"],
            "trace": state["trace"],
            "persistent_state": True,
            "execution_mode": "simulation",
            "model_requests": 0,
            "business_tools_executed": False,
        }

    def start(self, plan: dict) -> dict:
        plan = normalize_plan(plan)
        self.directory.mkdir(parents=True, exist_ok=True)
        task_id = str(uuid4())
        path = self.database_path(task_id)
        # Exclusive creation never replaces another task or an application database.
        with path.open("xb"):
            pass
        with self._connection(task_id) as conn, tracing_context(enabled=False):
            conn.execute(
                "CREATE TABLE task_metadata (task_id TEXT PRIMARY KEY, graph_version INTEGER NOT NULL, created_at TEXT NOT NULL, plan_json TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO task_metadata VALUES (?, ?, ?, ?)",
                (
                    task_id,
                    GRAPH_VERSION,
                    datetime.now(UTC).isoformat(),
                    json.dumps(plan, ensure_ascii=False),
                ),
            )
            conn.commit()
            meta = self._metadata(conn, task_id)
            graph = self._graph(conn)
            config = self._config(task_id)
            graph.invoke(self._seed(meta), config, durability="sync")
            return self._view(graph.get_state(config), meta)

    def status(self, task_id: str) -> dict:
        with self._connection(task_id) as conn, tracing_context(enabled=False):
            meta = self._metadata(conn, task_id)
            graph = self._graph(conn)
            return self._view(graph.get_state(self._config(task_id)), meta)

    def resume(self, task_id: str, checkpoint_id: str) -> dict:
        with self._connection(task_id) as conn, tracing_context(enabled=False):
            meta = self._metadata(conn, task_id)
            graph = self._graph(conn)
            config = self._config(task_id)
            view = self._view(graph.get_state(config), meta)
            if view["phase"] == "finished":
                return view
            if not checkpoint_id or checkpoint_id != view["checkpoint_id"]:
                raise StoreError("stale_checkpoint")
            if view["phase"] != "paused":
                raise StoreError("use_recover")
            graph.invoke(Command(resume=True), config, durability="sync")
            return self._view(graph.get_state(config), meta)

    def recover(self, task_id: str) -> dict:
        with self._connection(task_id) as conn, tracing_context(enabled=False):
            meta = self._metadata(conn, task_id)
            graph = self._graph(conn)
            config = self._config(task_id)
            view = self._view(graph.get_state(config), meta)
            if view["phase"] in {"paused", "finished"}:
                return view
            seed = self._seed(meta) if view["phase"] == "initializing" else None
            graph.invoke(seed, config, durability="sync")
            return self._view(graph.get_state(config), meta)
