"""Bounded knowledge evidence with a timeout-isolated Knowledge Hub adapter."""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HERE = Path(__file__).resolve().parent
DATA = HERE / "knowledge-data.json"
MAX_WORKER_BYTES = 65536
MAX_TEXT_CHARS = 1000
NO_EVIDENCE = "无法从当前检索证据确定。"


class KnowledgeError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchArguments(Contract):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=3, ge=1, le=5)

    @field_validator("query")
    @classmethod
    def nonblank_query(cls, value):
        if not value.strip():
            raise ValueError("blank_query")
        return value.strip()


class Function(Contract):
    name: Literal["search_knowledge"]
    arguments: str = Field(min_length=1, max_length=2048)


class Call(Contract):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    type: Literal["function"]
    function: Function


class Chunk(Contract):
    id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=20000)
    source: str = Field(min_length=1, max_length=240)
    chunk_index: int = Field(ge=0, le=1_000_000)
    distance: float = Field(ge=0, allow_inf_nan=False)

    @field_validator("id", "source")
    @classmethod
    def single_line_label(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("invalid_label")
        return value

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value):
        if not value.strip():
            raise ValueError("blank_text")
        return value


class Decision(Contract):
    status: Literal["answered", "insufficient_evidence"]
    answer: str = Field(min_length=1, max_length=3000)
    citations: list[str] = Field(max_length=5)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError("non_standard_json_constant")


def parse_json(raw):
    return json.loads(
        raw, object_pairs_hook=unique_object, parse_constant=reject_constant
    )


def validate_call(value):
    try:
        call = Call.model_validate(value)
        return call, SearchArguments.model_validate(parse_json(call.function.arguments))
    except (ValueError, TypeError, RecursionError):
        raise KnowledgeError("invalid_tool_call_or_arguments") from None


def verify_answer(raw, evidence):
    try:
        if not isinstance(raw, str) or len(raw) > 8000:
            raise ValueError
        answer = Decision.model_validate(parse_json(raw))
        available = {row["citation"] for row in evidence}
        cited = set(answer.citations)
        labels_in_text = set(re.findall(r"\[(K[0-9]+)\]", answer.answer))
        if len(cited) != len(answer.citations) or not cited <= available:
            raise ValueError
        if cited != labels_in_text:
            raise ValueError
        if answer.status == "answered":
            if not cited or not answer.answer.strip():
                raise ValueError
        elif cited or answer.answer != NO_EVIDENCE:
            raise ValueError
        return answer.model_dump()
    except (ValueError, TypeError, RecursionError, KeyError):
        raise KnowledgeError("invalid_answer_or_citations") from None


def tool_definitions():
    return [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "在应用指定的 Knowledge Hub 中检索片段及来源；只传查询词和条数，不接受路径、URL、集合名或其它操作。",
                "parameters": SearchArguments.model_json_schema(),
            },
        }
    ]


def fixture_records(case):
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if case == "empty":
        return []
    records = [dict(data["documents"][0], distance=0.2)]
    if case == "injection":
        records.append(dict(data["injection_document"], distance=0.5))
    return records


class FixtureRetriever:
    def __init__(self, case="supported"):
        if case not in {"supported", "empty", "injection"}:
            raise ValueError("unknown_fixture")
        self.case = case

    def __call__(self, query, *, top_k):
        return fixture_records(self.case)[:top_k]


class HubRetriever:
    """Each retrieval runs in its own child; timeout kills that child."""

    def __init__(
        self, backend="hub-demo", *, empty_demo=False, timeout_seconds=45, runner=None
    ):
        if backend not in {"hub-demo", "hub"}:
            raise ValueError("invalid_backend")
        if type(empty_demo) is not bool or (backend == "hub" and empty_demo):
            raise ValueError("invalid_empty_demo")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 45
        ):
            raise ValueError("invalid_timeout")
        self.backend = backend
        self.empty_demo = empty_demo
        self.timeout_seconds = timeout_seconds
        self.runner = runner or subprocess.run

    def __call__(self, query, *, top_k):
        request = SearchArguments(query=query, top_k=top_k)
        command = [
            sys.executable,
            "-B",
            str(HERE / "hub_worker.py"),
            "--backend",
            self.backend,
        ]
        if self.empty_demo:
            command.append("--empty-demo")
        # The retrieval process needs no LLM credentials or arbitrary PYTHONPATH.
        allowed = {
            "SYSTEMROOT",
            "WINDIR",
            "PATH",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMDATA",
        }
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        env.update(
            PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", ANONYMIZED_TELEMETRY="False"
        )
        try:
            result = self.runner(
                command,
                input=request.model_dump_json(),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=self.timeout_seconds,
                cwd=HERE,
                env=env,
            )
            if len(result.stdout.encode("utf-8")) > MAX_WORKER_BYTES:
                raise KnowledgeError("retrieval_response_too_large")
            payload = parse_json(result.stdout)
            if result.returncode != 0 or payload.get("status") != "ok":
                known = {
                    "embedding_cache_missing",
                    "knowledge_store_missing",
                    "knowledge_collection_missing",
                }
                code = payload.get("error")
                raise KnowledgeError(code if code in known else "retrieval_failed")
            if set(payload) != {"status", "chunks"} or not isinstance(
                payload["chunks"], list
            ):
                raise ValueError
            return payload["chunks"]
        except subprocess.TimeoutExpired:
            raise KnowledgeError("retrieval_timeout") from None
        except KnowledgeError:
            raise
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            raise KnowledgeError("retrieval_failed") from None


class KnowledgeTool:
    def __init__(self, search, *, backend_label="fixture"):
        self.search = search
        self.backend_label = backend_label

    def query(self, parameters):
        try:
            args = SearchArguments.model_validate(parameters)
        except (ValueError, TypeError, RecursionError):
            raise KnowledgeError("invalid_query_parameters") from None
        try:
            raw = self.search(args.query, top_k=args.top_k)
        except KnowledgeError:
            raise
        except Exception:
            raise KnowledgeError("retrieval_failed") from None
        try:
            if not isinstance(raw, list) or len(raw) > args.top_k:
                raise ValueError
            rows = [Chunk.model_validate(row) for row in raw]
            evidence, by_id, seen_text = [], {}, set()
            for row in sorted(rows, key=lambda item: item.distance):
                identity = row.model_dump()
                if row.id in by_id:
                    if by_id[row.id] != identity:
                        raise ValueError
                    continue
                by_id[row.id] = identity
                key = (row.source, row.text.strip())
                if key in seen_text:
                    continue
                seen_text.add(key)
                evidence.append(
                    {
                        **identity,
                        "text": row.text[:MAX_TEXT_CHARS],
                        "text_truncated": len(row.text) > MAX_TEXT_CHARS,
                        "citation": f"K{len(evidence) + 1}",
                    }
                )
        except (ValueError, TypeError, RecursionError):
            raise KnowledgeError("invalid_retrieval_result") from None
        return {
            "backend": self.backend_label,
            "query": args.query,
            "data_status": "evidence_found" if evidence else "no_evidence",
            "evidence": evidence,
            "returned_count": len(evidence),
            "retrieval_only": True,
            "content_is_untrusted_data": True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--backend", choices=["fixture", "hub-demo", "hub"], default="fixture"
    )
    args = parser.parse_args()
    search = (
        FixtureRetriever() if args.backend == "fixture" else HubRetriever(args.backend)
    )
    try:
        result = KnowledgeTool(search, backend_label=args.backend).query(
            {"query": args.query, "top_k": args.top_k}
        )
    except KnowledgeError as exc:
        print(json.dumps({"status": "rejected", "error": exc.code}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
