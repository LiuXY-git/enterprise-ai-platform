"""Offline graph, schema and HTTP adapter tests; no model credentials required."""

import copy
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("langgraph", reason="Install the isolated Day 59 requirements")
pytest.importorskip("dotenv", reason="Install the isolated Day 59 requirements")

import httpx  # noqa: E402
from chat_planner import ChatPlanner  # noqa: E402
from plan_schema import parse_plan  # noqa: E402
from task_planner import DEMO_GOAL, mock_generator, run_task  # noqa: E402

FIXTURES = json.loads(
    Path(__file__).with_name("mock-responses.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.mark.parametrize(
    "case,status,reason",
    [
        ("normal", "planned", "plan_validated"),
        ("clarify", "waiting_for_input", "model_requests_clarification"),
        ("invalid", "failed", "invalid_model_output"),
        ("provider-error", "failed", "provider_timeout"),
    ],
)
def test_graph_decisions(case, status, reason):
    result = run_task(DEMO_GOAL, mock_generator(case), mode="mock")
    state = result["state"]
    assert state["status"] == status
    assert state["stop_reason"] == reason
    assert state["planning_attempts"] == 1
    assert state["trace"][0] == "validate_input" and state["trace"][-1] == "finish"
    assert ("validate_plan" in state["trace"]) == (case != "provider-error")
    assert (state["plan"] is not None) == (case == "normal")
    assert bool(state["questions"]) == (case == "clarify")
    assert "raw_output" not in state
    assert result["model_requests"] == 0
    assert result["task_executed"] is result["tools_executed"] is False


@pytest.mark.parametrize(
    "goal,status",
    [
        ("", "waiting_for_input"),
        ("  \n", "waiting_for_input"),
        ("a" * 2001, "failed"),
        (42, "failed"),
    ],
)
def test_invalid_or_empty_input_never_calls_model(goal, status):
    def must_not_call(goal):
        pytest.fail("Model should not be called")

    result = run_task(goal, must_not_call, mode="mock")
    assert result["state"]["status"] == status
    assert result["state"]["planning_attempts"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown-field",
        "unknown-action",
        "duplicate-id",
        "forward-dependency",
        "duplicate-dependency",
        "empty-plan",
        "too-many-steps",
        "numeric-text",
        "blank-text",
        "long-text",
        "questions-with-plan",
        "clarify-with-steps",
        "clarify-no-questions",
    ],
)
def test_malformed_plans_are_rejected(mutation):
    plan = copy.deepcopy(FIXTURES["normal"])
    if mutation == "unknown-field":
        plan["command"] = "do-something"
    elif mutation == "unknown-action":
        plan["steps"][0]["action"] = "send_email"
    elif mutation == "duplicate-id":
        plan["steps"][1]["id"] = "S1"
    elif mutation == "forward-dependency":
        plan["steps"][0]["depends_on"] = ["S2"]
    elif mutation == "duplicate-dependency":
        plan["steps"][2]["depends_on"] = ["S1", "S1"]
    elif mutation == "empty-plan":
        plan["steps"] = []
    elif mutation == "too-many-steps":
        plan["steps"] *= 2
    elif mutation == "numeric-text":
        plan["steps"][0]["description"] = 123
    elif mutation == "blank-text":
        plan["summary"] = "   "
    elif mutation == "long-text":
        plan["summary"] = "a" * 301
    elif mutation == "questions-with-plan":
        plan["questions"] = ["Unnecessary question"]
    elif mutation == "clarify-with-steps":
        plan["decision"] = "clarify"
        plan["questions"] = ["Question"]
    else:
        plan.update(decision="clarify", steps=[], questions=[])
    with pytest.raises(ValueError):
        parse_plan(json.dumps(plan))


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{}",
        "[]",
        "null",
        '{"a":1,"a":2}',
        '{"a":NaN}',
        "x" * 16001,
        FIXTURES["invalid"],
    ],
)
def test_invalid_json_is_rejected(raw):
    with pytest.raises(ValueError):
        parse_plan(raw)


def config(provider="qwen"):
    return SimpleNamespace(
        provider=provider,
        model="test-model",
        api_key="test-secret",
        base_url="https://provider.invalid/v1",
    )


def envelope(content=None, finish="stop"):
    return {
        "choices": [
            {
                "finish_reason": finish,
                "message": {
                    "content": content
                    if content is not None
                    else json.dumps(FIXTURES["normal"])
                },
            }
        ]
    }


@pytest.mark.parametrize("provider", ["qwen", "deepseek"])
def test_http_contract_and_plan_validation(provider):
    calls = []

    def handler(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-secret"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["messages"][1]["content"] == DEMO_GOAL
        assert "tools" not in payload
        assert payload["max_tokens"] == 1800
        assert ("enable_thinking" in payload) == (provider == "qwen")
        return httpx.Response(200, json=envelope())

    adapter = ChatPlanner(
        config_loader=lambda: config(provider), transport=httpx.MockTransport(handler)
    )
    result = run_task(DEMO_GOAL, adapter, mode="mock-transport")
    assert result["state"]["status"] == "planned"
    assert len(calls) == adapter.requests == result["model_requests"] == 1
    assert "test-secret" not in json.dumps(result)


@pytest.mark.parametrize("status", [301, 401, 429, 500])
def test_http_errors_do_not_retry_redirect_or_expose_response(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="test-secret-sensitive-provider-body",
            headers={"location": "https://other.invalid"},
        )

    adapter = ChatPlanner(config_loader=config, transport=httpx.MockTransport(handler))
    result = run_task(DEMO_GOAL, adapter, mode="mock-transport")
    assert len(calls) == 1
    assert result["state"]["stop_reason"] == f"provider_http_{status}"
    assert "test-secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("timeout", "provider_timeout"),
        ("network", "provider_network_error"),
        ("oversized", "response_too_large"),
        ("bad-json", "provider_invalid_response"),
        ("no-choices", "provider_invalid_response"),
        ("truncated", "provider_incomplete_response"),
        ("empty", "provider_empty_response"),
        ("tool-call", "unexpected_tool_call"),
    ],
)
def test_provider_failures(kind, reason):
    def handler(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("secret", request=request)
        if kind == "network":
            raise httpx.ConnectError("secret", request=request)
        if kind == "oversized":
            return httpx.Response(200, content=b"x" * 65537)
        if kind == "bad-json":
            return httpx.Response(200, text="secret-not-json")
        if kind == "no-choices":
            return httpx.Response(200, json={"choices": []})
        payload = envelope(
            "" if kind == "empty" else None, "length" if kind == "truncated" else "stop"
        )
        if kind == "tool-call":
            payload["choices"][0]["message"]["tool_calls"] = [{"id": "call-1"}]
        return httpx.Response(200, json=payload)

    adapter = ChatPlanner(config_loader=config, transport=httpx.MockTransport(handler))
    result = run_task(DEMO_GOAL, adapter, mode="mock-transport")
    assert result["state"]["status"] == "failed"
    assert result["state"]["stop_reason"] == reason
    assert result["model_requests"] == 1
    assert "secret" not in json.dumps(result)


def test_configuration_failure_has_no_http_attempt():
    def missing_config():
        raise RuntimeError("sensitive config")

    adapter = ChatPlanner(config_loader=missing_config)
    result = run_task(DEMO_GOAL, adapter, mode="mock-transport")
    assert result["state"]["stop_reason"] == "configuration_invalid"
    assert result["model_requests"] == 0
    assert "sensitive" not in json.dumps(result)


def test_tracing_is_disabled_and_runs_do_not_share_state(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    generate = mock_generator("normal")
    assert run_task(DEMO_GOAL, generate, mode="mock") == run_task(
        DEMO_GOAL, generate, mode="mock"
    )


def test_default_cli_is_offline_and_does_not_load_environment(monkeypatch, capsys):
    import sys

    from task_planner import main

    from backend.app import settings

    def forbidden(*args, **kwargs):
        pytest.fail("Default mock CLI must not load credentials")

    monkeypatch.setattr(settings, "load_environment", forbidden)
    monkeypatch.setattr(sys, "argv", ["task_planner.py"])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "mock" and result["model_requests"] == 0


def test_live_cli_requires_explicit_goal(monkeypatch):
    import sys

    from task_planner import main

    monkeypatch.setattr(sys, "argv", ["task_planner.py", "--live"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_failed_cli_returns_nonzero_and_valid_json(monkeypatch, capsys):
    import sys

    from task_planner import main

    monkeypatch.setattr(sys, "argv", ["task_planner.py", "--mock-case", "invalid"])
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["state"]["status"] == "failed"


def test_reused_adapter_reports_requests_per_task():
    adapter = ChatPlanner(
        config_loader=config,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=envelope())
        ),
    )
    first = run_task(DEMO_GOAL, adapter, mode="mock-transport")
    second = run_task(DEMO_GOAL, adapter, mode="mock-transport")
    empty = run_task("", adapter, mode="mock-transport")
    assert first["model_requests"] == second["model_requests"] == 1
    assert empty["model_requests"] == 0
    assert adapter.requests == 2
