"""Composition tests use real fictional SQLite and zero external requests."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from multi_tool_agent import (  # noqa: E402
    CASES,
    FixtureChat,
    available_citations,
    next_state,
    run_cases,
    run_session,
    verify_report,
)
from tool_registry import (  # noqa: E402
    KNOWLEDGE,
    NAMES,
    SQL,
    WEATHER,
    OrchestrationError,
    Registry,
    definitions,
    knowledge,
    make_registry,
    sales,
    scope_for,
    weather,
)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "fictional.sqlite"
    sales.create_demo(path)
    return path


def call(name, arguments, call_id="call_custom"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def tool_reply(calls):
    return {
        "finish_reason": "tool_calls",
        "message": {"role": "assistant", "content": None, "tool_calls": calls},
    }


class ScriptChat:
    requests = 0
    metadata = {"provider": "test"}

    def __init__(self, replies):
        self.replies = iter(replies)
        self.choices = []

    def __call__(self, messages, tools, *, tool_choice):
        self.requests += 1
        self.choices.append(tool_choice)
        return next(self.replies)


class MutatingChat:
    requests = 0
    metadata = {}

    def __init__(self, case="full", mutate=None, weather_first=False):
        self.fixture = FixtureChat(case, weather_first=weather_first)
        self.mutate = mutate or (lambda reply, turn: reply)
        self.tool_lists = []
        self.choices = []

    def __call__(self, messages, tools, *, tool_choice):
        self.requests += 1
        self.choices.append(tool_choice)
        self.tool_lists.append([tool["function"]["name"] for tool in tools])
        return self.mutate(
            self.fixture(messages, tools, tool_choice=tool_choice), self.requests
        )


@pytest.mark.parametrize("case", list(CASES))
def test_five_outcomes_and_sql_remains_unchanged(database, case):
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = run_cases([case], database)[0]["result"]
    assert (
        result["status"] == CASES[case] and result["stop_reason"] == "report_validated"
    )
    assert result["model_requests"] == result["api_network_requests"] == 0
    assert result["citation_links_verified"] and not result["answer_semantics_verified"]
    assert (
        not result["external_business_actions"] and not result["persistent_agent_state"]
    )
    assert len(result["receipts"]) == (1 if case in {"no_sales", "sql_error"} else 3)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    messages = result["messages"]
    tool_messages = [row for row in messages if row["role"] == "tool"]
    ids = [row["id"] for row in result["receipts"]]
    assert len(ids) == len(set(ids))
    assert [row["tool_call_id"] for row in tool_messages] == ids
    assert [json.loads(row["content"]) for row in tool_messages] == result["receipts"]
    if case == "full":
        assert result["receipts"][0]["result"]["total_yuan"] == "3000.00"
        assert result["receipts"][0]["result"]["truncated"]
    if case in {"weather_timeout", "sql_error"}:
        assert any(row["status"] == "error" for row in result["receipts"])
    if case == "knowledge_empty":
        assert result["tool_executions"] == 3 and result["status"] == "partial"


@pytest.mark.parametrize("weather_first", [False, True])
def test_valid_order_is_model_selected_after_sales(database, weather_first):
    chat = MutatingChat(weather_first=weather_first)
    result = run_session("brief", chat, make_registry(database, "full"))
    expected = [SQL, WEATHER, KNOWLEDGE] if weather_first else list(NAMES)
    assert [row["name"] for row in result["receipts"]] == expected
    assert result["status"] == "completed" and result["model_requests"] == 4
    assert chat.choices == ["auto", "auto", "auto", "none"]
    assert chat.tool_lists[0] == [SQL]
    assert set(chat.tool_lists[1]) == {KNOWLEDGE, WEATHER}
    assert len(chat.tool_lists[2]) == 1
    policy = next(row for row in result["receipts"] if row["name"] == KNOWLEDGE)
    assert f"{policy['source_id']}:K1" in result["report"]["citations"]


def test_weather_failure_does_not_block_independent_knowledge(database):
    chat = MutatingChat("weather_timeout", weather_first=True)
    result = run_session("brief", chat, make_registry(database, "weather_timeout"))
    assert result["status"] == "partial"
    assert [row["status"] for row in result["receipts"]] == ["ok", "error", "ok"]
    assert result["receipts"][2]["name"] == KNOWLEDGE and result["tool_executions"] == 2


@pytest.mark.parametrize("case", ["no_sales", "sql_error"])
def test_early_exit_never_touches_downstream_tools(database, case):
    registry = make_registry(database, case)

    class Forbidden:
        def query(self, params):
            pytest.fail("downstream must not execute")

    registry.bindings[KNOWLEDGE] = Forbidden()
    registry.bindings[WEATHER] = Forbidden()
    chat = MutatingChat(case)
    result = run_session("brief", chat, registry)
    assert result["status"] == CASES[case] and result["model_requests"] == 2
    assert chat.choices == ["auto", "none"]


@pytest.mark.parametrize(
    "name,params",
    [
        (SQL, {"year": 2025, "month": 9, "limit": 2}),
        (SQL, {"year": 2026, "month": 8, "limit": 2}),
        (SQL, {"year": 2026, "month": 9, "limit": 5}),
        (SQL, {"year": 2026, "month": 9, "limit": 2, "customer_id": "C001"}),
        (WEATHER, {"city": "beijing", "days": 1}),
        (WEATHER, {"city": "shanghai", "days": 3}),
    ],
)
def test_valid_tool_arguments_still_cannot_drift_scope(database, name, params):
    with pytest.raises(OrchestrationError, match="tool_arguments_out_of_scope"):
        make_registry(database, "full").validate(call(name, params))


@pytest.mark.parametrize(
    "raw",
    [
        {},
        None,
        [],
        {"function": {"name": []}},
        call("send_email", {}),
        call("http_request", {"url": "http://localhost"}),
        call(KNOWLEDGE, {"query": "hotel", "path": "C:/secret"}),
        call(WEATHER, {"city": "shanghai", "days": True}),
        call(
            SQL,
            {"year": 2026, "month": 9, "limit": 2, "sql": "DELETE FROM sales_orders"},
        ),
    ],
)
def test_bad_call_contract(database, raw):
    with pytest.raises(OrchestrationError, match="invalid_tool_call_or_arguments"):
        make_registry(database, "full").validate(raw)


@pytest.mark.parametrize(
    "name,params",
    [(KNOWLEDGE, {"query": "hotel"}), (WEATHER, {"city": "shanghai", "days": 1})],
)
def test_dependents_cannot_run_before_sales(database, name, params):
    result = run_session(
        "brief",
        ScriptChat([tool_reply([call(name, params)])]),
        make_registry(database, "full"),
    )
    assert (
        result["stop_reason"] == "tool_not_allowed_in_state"
        and result["tool_attempts"] == 0
    )


def test_multiple_calls_rejected_before_any_execute(database):
    first = call(SQL, scope_for("full")["sales"])
    result = run_session(
        "brief",
        ScriptChat(
            [tool_reply([first, call(KNOWLEDGE, {"query": "hotel"}, "second")])]
        ),
        make_registry(database, "full"),
    )
    assert result["stop_reason"] == "multiple_tool_calls_not_supported"
    assert result["tool_attempts"] == 0 and not result["receipts"]


def test_repeat_tool_rejected_without_reexecution(database):
    params = scope_for("full")["sales"]
    result = run_session(
        "brief",
        ScriptChat(
            [
                tool_reply([call(SQL, params, "first")]),
                tool_reply([call(SQL, params, "second")]),
            ]
        ),
        make_registry(database, "full"),
    )
    assert (
        result["stop_reason"] == "tool_not_allowed_in_state"
        and result["tool_attempts"] == 1
    )


def test_duplicate_call_id_rejected(database):
    result = run_session(
        "brief",
        ScriptChat(
            [
                tool_reply([call(SQL, scope_for("full")["sales"])]),
                tool_reply([call(KNOWLEDGE, {"query": "hotel"})]),
            ]
        ),
        make_registry(database, "full"),
    )
    assert (
        result["stop_reason"] == "duplicate_tool_call_id"
        and result["tool_attempts"] == 1
    )


@pytest.mark.parametrize("at_turn", [1, 2, 3])
def test_premature_final_cannot_claim_completion(database, at_turn):
    def mutate(reply, turn):
        if turn == at_turn:
            return {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Done"},
            }
        return reply

    result = run_session(
        "brief", MutatingChat(mutate=mutate), make_registry(database, "full")
    )
    assert result["stop_reason"] == "required_tools_missing"
    assert result["tool_attempts"] == at_turn - 1


def test_tool_call_after_three_attempts_cannot_execute(database):
    def mutate(reply, turn):
        return (
            tool_reply([call(WEATHER, {"city": "shanghai", "days": 1}, "fourth")])
            if turn == 4
            else reply
        )

    chat = MutatingChat(mutate=mutate)
    result = run_session("brief", chat, make_registry(database, "full"))
    assert (
        result["stop_reason"] == "tool_budget_exhausted"
        and result["tool_attempts"] == 3
    )
    assert result["model_requests"] == 4


@pytest.fixture
def completed(database):
    return run_cases(["full"], database)[0]["result"]


@pytest.mark.parametrize(
    "updates",
    [
        {"status": "partial"},
        {"status": "success"},
        {"summary": "no citations"},
        {"citations": []},
        {"citations": ["T1", "T2:K1", "T3", "T3"]},
        {"citations": ["T1", "T2:K99", "T3"], "summary": "x[T1][T2:K99][T3]"},
        {"citations": ["T1", "T2:K1", "T9"], "summary": "x[T1][T2:K1][T9]"},
        {"citations": ["T1", "T2", "T3"], "summary": "x[T1][T2][T3]"},
        {"citations": ["T1", "T2:K1"], "summary": "x[T1][T2:K1]"},
        {"extra": "forbidden"},
        {"summary": "x" * 5001},
    ],
)
def test_report_status_coverage_and_citations(completed, updates):
    report = copy.deepcopy(completed["report"])
    report.update(updates)
    with pytest.raises(OrchestrationError, match="invalid_report_or_citations"):
        verify_report(json.dumps(report), completed["receipts"])


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "{}",
        "[]",
        "not json",
        "```json\n{}\n```",
        '{"status":"completed","status":"completed"}',
    ],
)
def test_invalid_report_json(completed, raw):
    with pytest.raises(OrchestrationError):
        verify_report(raw, completed["receipts"])


def test_cross_tool_knowledge_citation_rejected(completed):
    report = completed["report"]
    report["summary"] = "x[T1:K1][T2:K1][T3]"
    report["citations"] = ["T1:K1", "T2:K1", "T3"]
    with pytest.raises(OrchestrationError):
        verify_report(json.dumps(report), completed["receipts"])


def test_failure_cannot_be_reported_as_success(database):
    result = run_cases(["weather_timeout"], database)[0]["result"]
    report = result["report"]
    report["status"] = "completed"
    with pytest.raises(OrchestrationError):
        verify_report(json.dumps(report), result["receipts"])


def test_citation_validation_does_not_prove_summary_facts(completed):
    report = completed["report"]
    report["summary"] = "错误金额99999元[T1]，错误制度[T2:K1]，错误天气[T3]"
    assert (
        verify_report(json.dumps(report), completed["receipts"])["status"]
        == "completed"
    )
    assert not completed["answer_semantics_verified"]


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("private path and secret"),
        sales.SalesError("private_secret_token"),
        weather.WeatherError("api_http_999"),
    ],
)
def test_exception_sanitization(database, exception):
    registry = make_registry(database, "full")

    class Broken:
        def query(self, params):
            raise exception

    registry.bindings[SQL] = Broken()
    result = run_session("brief", FixtureChat("full"), registry)
    assert (
        result["status"] == "failed"
        and result["receipts"][0]["error"] == "tool_execution_failed"
    )
    assert "secret" not in json.dumps(result) and "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {"order_count": True, "data_status": "ok"},
        {"order_count": -1, "data_status": "ok"},
        {"order_count": 0, "data_status": "ok"},
        {"text": "x" * 12001},
    ],
)
def test_bad_sales_result_cannot_advance_graph(database, value):
    registry = make_registry(database, "full")

    class Broken:
        def query(self, params):
            return value

    registry.bindings[SQL] = Broken()
    result = run_session("brief", FixtureChat("full"), registry)
    assert result["status"] == "failed" and result["tool_attempts"] == 1


@pytest.mark.parametrize(
    "value",
    [
        {"evidence": None, "returned_count": 0},
        {"evidence": [], "returned_count": 1},
        {"evidence": [{"citation": "K99"}], "returned_count": 1},
        {"evidence": [{"citation": "K1"}, {"citation": "K1"}], "returned_count": 2},
    ],
)
def test_bad_knowledge_result_becomes_partial(database, value):
    registry = make_registry(database, "full")

    class Broken:
        def query(self, params):
            return value

    registry.bindings[KNOWLEDGE] = Broken()
    result = run_session("brief", FixtureChat("full"), registry)
    assert result["status"] == "partial" and result["tool_attempts"] == 3


def test_chat_cannot_mutate_audit_log(database):
    fixture = FixtureChat("full")

    def chat(messages, tools, *, tool_choice):
        reply = fixture(messages, tools, tool_choice=tool_choice)
        messages.clear()
        return reply

    result = run_session("brief", chat, make_registry(database, "full"))
    assert result["status"] == "completed" and len(result["receipts"]) == 3


def test_context_budget_stops_before_request(database, monkeypatch):
    import multi_tool_agent

    monkeypatch.setattr(multi_tool_agent, "MAX_CONTEXT_CHARS", 10)
    chat = ScriptChat([])
    result = run_session("brief", chat, make_registry(database, "full"))
    assert result["stop_reason"] == "context_budget_exceeded" and chat.requests == 0


@pytest.mark.parametrize("goal", [None, "", " ", 123, "x" * 2001])
def test_invalid_goal_no_execution(database, goal):
    result = run_session(goal, ScriptChat([]), make_registry(database, "full"))
    assert result["stop_reason"] == "invalid_input" and result["tool_attempts"] == 0


def test_registry_requires_complete_application_bindings():
    with pytest.raises(ValueError):
        Registry({}, scope_for("full"))


def test_definitions_use_existing_schemas():
    assert [item["function"]["name"] for item in definitions()] == list(NAMES)
    assert definitions([KNOWLEDGE]) == knowledge.tool_definitions()
    assert definitions([WEATHER]) == weather.tool_definitions()


def test_state_and_reference_helpers(completed):
    assert next_state([]) == ([SQL], None)
    assert next_state(completed["receipts"]) == ([], "completed")
    assert available_citations(completed["receipts"]) == {"T1", "T2", "T2:K1", "T3"}


@pytest.mark.parametrize(
    "arguments",
    [
        ["--live"],
        ["--live", "--case", "no_sales"],
        ["--live", "--case", "weather_timeout"],
        ["--env-file", "missing.env"],
        ["--case", "full", "--check-all"],
    ],
)
def test_cli_guards(arguments):
    result = subprocess.run(
        [sys.executable, "-B", str(HERE / "multi_tool_agent.py"), *arguments],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_live_failure_case_is_not_allowed(database):
    with pytest.raises(ValueError):
        make_registry(database, "weather_timeout", live=True)
