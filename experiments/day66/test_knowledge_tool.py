"""Offline contract and failure-path tests; no model, embedding or business data."""

import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from knowledge_agent import CASES, FixtureChat, run_cases, run_session  # noqa: E402
from knowledge_tool import (  # noqa: E402
    NO_EVIDENCE,
    FixtureRetriever,
    HubRetriever,
    KnowledgeError,
    KnowledgeTool,
    fixture_records,
    tool_definitions,
    validate_call,
    verify_answer,
)


def call(arguments=None, **updates):
    value = {
        "id": "call_1",
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "arguments": json.dumps(
                arguments if arguments is not None else {"query": "hotel"}
            ),
        },
    }
    value.update(updates)
    return value


def evidence():
    return KnowledgeTool(FixtureRetriever()).query({"query": "hotel"})["evidence"]


def decision(**updates):
    value = {"status": "answered", "answer": "虚构制度450元[K1]。", "citations": ["K1"]}
    value.update(updates)
    return json.dumps(value, ensure_ascii=False)


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"query": ""},
        {"query": "  "},
        {"query": True},
        {"query": 42},
        {"query": "a" * 301},
        {"query": "q", "top_k": 0},
        {"query": "q", "top_k": 6},
        {"query": "q", "top_k": True},
        {"query": "q", "top_k": "3"},
        {"query": "q", "top_k": 2.0},
        {"query": "q", "url": "https://example.com"},
        {"query": "q", "path": "C:/secret"},
        {"query": "q", "collection": "private"},
        [],
        None,
    ],
)
def test_invalid_parameters_never_retrieve(arguments):
    calls = []
    tool = KnowledgeTool(lambda *a, **k: calls.append(1))
    with pytest.raises(KnowledgeError, match="invalid_query_parameters"):
        tool.query(arguments)
    assert not calls


@pytest.mark.parametrize(
    "raw",
    [
        '{"query":"a","query":"b"}',
        '{"query":NaN}',
        '{"query":Infinity}',
        "{}",
        "[]",
        "null",
        "{",
        '"query"',
    ],
)
def test_bad_argument_json(raw):
    value = call()
    value["function"]["arguments"] = raw
    with pytest.raises(KnowledgeError, match="invalid_tool_call"):
        validate_call(value)


@pytest.mark.parametrize(
    "update",
    [
        {"id": "bad\nid"},
        {"id": "a" * 129},
        {"type": "shell"},
        {"extra": 1},
        {"function": {"name": "delete_all_files", "arguments": "{}"}},
    ],
)
def test_call_allowlist(update):
    with pytest.raises(KnowledgeError):
        validate_call(call(**update))


def test_schema_matches_runtime():
    schema = tool_definitions()[0]["function"]["parameters"]
    assert not schema["additionalProperties"] and set(schema["properties"]) == {
        "query",
        "top_k",
    }
    _, args = validate_call(call({"query": "  hotel  ", "top_k": 5}))
    assert args.query == "hotel" and args.top_k == 5


@pytest.mark.parametrize(
    "update",
    [
        {"distance": float("nan")},
        {"distance": float("inf")},
        {"distance": -1.0},
        {"source": ""},
        {"source": "x\nsecret"},
        {"id": " "},
        {"id": "x\x00"},
        {"text": " "},
        {"text": "a" * 20001},
        {"chunk_index": -1},
        {"chunk_index": True},
        {"chunk_index": "0"},
        {"unknown": 1},
    ],
)
def test_invalid_evidence(update):
    row = fixture_records("supported")[0]
    row.update(update)
    with pytest.raises(KnowledgeError, match="invalid_retrieval_result"):
        KnowledgeTool(lambda *a, **k: [row]).query({"query": "q"})


@pytest.mark.parametrize(
    "raw", [None, {}, "secret", [None], [*fixture_records("supported")] * 6]
)
def test_invalid_result_envelope(raw):
    with pytest.raises(KnowledgeError, match="invalid_retrieval_result"):
        KnowledgeTool(lambda *a, **k: raw).query({"query": "q"})


def test_dedup_sort_truncate_and_identity():
    first = fixture_records("supported")[0]
    long = dict(first, id="long", text="x" * 1100, distance=0.1)
    tool = KnowledgeTool(
        lambda *a, **k: [first, long, first, dict(first, id="duplicate")]
    )
    rows = tool.query({"query": "q", "top_k": 5})["evidence"]
    assert len(rows) == 2 and rows[0]["id"] == "long" and rows[0]["citation"] == "K1"
    assert rows[0]["text_truncated"] and len(rows[0]["text"]) == 1000
    assert rows[1]["source"] == first["source"] and rows[1]["chunk_index"] == 0


def test_conflicting_id_rejected():
    row = fixture_records("supported")[0]
    with pytest.raises(KnowledgeError, match="invalid_retrieval_result"):
        KnowledgeTool(lambda *a, **k: [row, dict(row, text="changed")]).query(
            {"query": "q"}
        )


def test_backend_error_is_not_empty_or_leaked():
    def fail(*args, **kwargs):
        raise RuntimeError("secret-connection-string")

    with pytest.raises(KnowledgeError, match="^retrieval_failed$"):
        KnowledgeTool(fail).query({"query": "q"})


@pytest.mark.parametrize(
    "update",
    [
        {"citations": []},
        {"citations": ["K2"]},
        {"citations": ["K1", "K1"]},
        {"answer": "no reference"},
        {"answer": "wrong [K9]"},
        {"extra": True},
        {"status": "success"},
        {"answer": " "},
        {"citations": "K1"},
        {"status": "insufficient_evidence", "answer": "猜测450元", "citations": []},
    ],
)
def test_invalid_final_decisions(update):
    with pytest.raises(KnowledgeError, match="invalid_answer_or_citations"):
        verify_answer(decision(**update), evidence())


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "{}",
        "[]",
        "not json",
        "```json\n{}\n```",
        "x" * 8001,
        '{"status":"answered","status":"answered"}',
    ],
)
def test_invalid_final_json(raw):
    with pytest.raises(KnowledgeError):
        verify_answer(raw, evidence())


def test_empty_evidence_cannot_support_answer():
    with pytest.raises(KnowledgeError):
        verify_answer(decision(), [])
    value = verify_answer(
        decision(status="insufficient_evidence", answer=NO_EVIDENCE, citations=[]), []
    )
    assert value["status"] == "insufficient_evidence"


def test_citation_links_do_not_prove_semantics():
    # This deliberate counterexample documents exactly what citation validation proves.
    value = verify_answer(decision(answer="错误数字99999元[K1]"), evidence())
    assert value["status"] == "answered"


@pytest.mark.parametrize("timeout", [0, -1, 46, True, "4", float("nan"), float("inf")])
def test_timeout_configuration(timeout):
    with pytest.raises(ValueError):
        HubRetriever(timeout_seconds=timeout)


def test_worker_timeout():
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k["timeout"])

    with pytest.raises(KnowledgeError, match="retrieval_timeout"):
        HubRetriever(runner=timeout)("q", top_k=1)


@pytest.mark.parametrize(
    "stdout,code,expected",
    [
        ("private failure", 1, "retrieval_failed"),
        ("[]", 0, "retrieval_failed"),
        ('{"status":"ok","chunks":{}}', 0, "retrieval_failed"),
        ('{"status":"ok","chunks":[],"extra":1}', 0, "retrieval_failed"),
        ('{"status":"error","error":"secret"}', 1, "retrieval_failed"),
        (
            '{"status":"error","error":"knowledge_store_missing"}',
            1,
            "knowledge_store_missing",
        ),
        (
            '{"status":"error","error":"knowledge_collection_missing"}',
            1,
            "knowledge_collection_missing",
        ),
        (
            '{"status":"error","error":"embedding_cache_missing"}',
            1,
            "embedding_cache_missing",
        ),
        pytest.param(
            "x" * 65537, 0, "retrieval_response_too_large", id="oversized-worker-output"
        ),
    ],
)
def test_worker_failures(stdout, code, expected):
    def runner(*a, **k):
        return SimpleNamespace(stdout=stdout, returncode=code)

    with pytest.raises(KnowledgeError, match=f"^{expected}$"):
        HubRetriever(runner=runner)("q", top_k=1)


def test_worker_command_and_environment(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "must-not-pass")
    monkeypatch.setenv("PYTHONPATH", "must-not-pass")
    seen = []

    def runner(command, **kwargs):
        seen.append((command, kwargs))
        return SimpleNamespace(stdout='{"status":"ok","chunks":[]}', returncode=0)

    assert (
        HubRetriever(empty_demo=True, runner=runner)("$(not executed)", top_k=1) == []
    )
    command, kwargs = seen[0]
    assert "$(not executed)" not in command and command[-1] == "--empty-demo"
    assert not kwargs.get("shell", False) and kwargs["timeout"] == 45
    assert (
        "DASHSCOPE_API_KEY" not in kwargs["env"] and "PYTHONPATH" not in kwargs["env"]
    )
    assert json.loads(kwargs["input"])["query"] == "$(not executed)"


@pytest.mark.parametrize("case", list(CASES))
def test_fixtures_and_receipt_link(case):
    result = run_cases([case])[0]["result"]
    assert result["status"] == "completed" and result["model_requests"] == 0
    assert result["tool_executions"] == 1 and result["chat_turns"] == 2
    assert result["citation_links_verified"] and not result["answer_semantics_verified"]
    receipt = result["tool_results"][0]
    assert (
        receipt["id"]
        == result["messages"][2]["tool_calls"][0]["id"]
        == result["messages"][3]["tool_call_id"]
    )
    assert result["decision"]["status"] == (
        "insufficient_evidence" if case == "empty" else "answered"
    )


class ScriptChat:
    requests = 0
    metadata = {"provider": "test"}

    def __init__(self, replies):
        self.replies = iter(replies)
        self.choices = []

    def __call__(self, messages, tools, *, tool_choice):
        self.choices.append(tool_choice)
        self.requests += 1
        return next(self.replies)


def tool_reply(calls):
    return {
        "finish_reason": "tool_calls",
        "message": {"role": "assistant", "content": None, "tool_calls": calls},
    }


@pytest.mark.parametrize(
    "calls,stop",
    [
        ([call(), call(id="call_2")], "multiple_tool_calls_not_supported"),
        (
            [call(function={"name": "delete_all_files", "arguments": "{}"})],
            "invalid_tool_call_or_arguments",
        ),
        (
            [call({"query": "q", "url": "https://private"})],
            "invalid_tool_call_or_arguments",
        ),
    ],
)
def test_rejected_calls_do_not_execute(calls, stop):
    tool = KnowledgeTool(lambda *a, **k: pytest.fail("must not execute"))
    result = run_session("q", ScriptChat([tool_reply(calls)]), tool)
    assert result["stop_reason"] == stop and result["tool_attempts"] == 0


def test_injected_second_tool_cannot_execute():
    tool = KnowledgeTool(FixtureRetriever("injection"))
    chat = ScriptChat(
        [
            tool_reply([call()]),
            tool_reply(
                [call(function={"name": "delete_all_files", "arguments": "{}"})]
            ),
        ]
    )
    result = run_session("q", chat, tool)
    assert (
        result["stop_reason"] == "tool_budget_exhausted"
        and result["tool_executions"] == 1
    )
    assert chat.choices == ["auto", "none"] and result["model_requests"] == 2
    assert not result["external_business_actions"]


def test_hallucinated_source_fails_after_retrieval():
    final = {
        "finish_reason": "stop",
        "message": {
            "role": "assistant",
            "content": decision(answer="x[K9]", citations=["K9"]),
        },
    }
    result = run_session(
        "q",
        ScriptChat([tool_reply([call()]), final]),
        KnowledgeTool(FixtureRetriever()),
    )
    assert (
        result["status"] == "rejected"
        and result["stop_reason"] == "invalid_answer_or_citations"
    )
    assert result["tool_executions"] == 1 and not result["citation_links_verified"]


def test_empty_direct_answer_does_not_fabricate_evidence():
    final = {
        "finish_reason": "stop",
        "message": {"role": "assistant", "content": decision()},
    }
    result = run_session("q", ScriptChat([final]), KnowledgeTool(FixtureRetriever()))
    assert result["status"] == "rejected" and result["tool_executions"] == 0


@pytest.mark.parametrize("goal", [None, "", " ", 42, "x" * 2001])
def test_invalid_goal_has_no_model_request(goal):
    chat = ScriptChat([])
    result = run_session(goal, chat, KnowledgeTool(FixtureRetriever()))
    assert result["stop_reason"] == "invalid_input" and chat.requests == 0


@pytest.mark.parametrize(
    "kwargs", [{"live": True}, {"live": True, "backend": "hub"}, {"backend": "hub"}]
)
def test_live_cannot_send_production_knowledge(kwargs):
    with pytest.raises(ValueError):
        run_cases(["supported"], **kwargs)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--live"],
        ["--live", "--case", "supported"],
        ["--backend", "hub"],
        ["--env-file", "missing.env"],
        ["--case", "supported", "--check-all"],
        ["--backend", "hub-demo", "--case", "injection"],
        ["--backend", "hub-demo", "--check-all"],
    ],
)
def test_cli_guards(arguments):
    result = subprocess.run(
        [sys.executable, "-B", str(HERE / "knowledge_agent.py"), *arguments],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_chat_cannot_mutate_audit_messages():
    original = FixtureChat("supported")

    def chat(messages, tools, *, tool_choice):
        reply = original(messages, tools, tool_choice=tool_choice)
        messages.clear()
        return copy.deepcopy(reply)

    result = run_session("q", chat, KnowledgeTool(FixtureRetriever()))
    assert result["status"] == "completed" and len(result["messages"]) == 5
