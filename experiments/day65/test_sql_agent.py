"""Offline protocol integration with real temporary SQLite SELECTs."""

import copy
import json
import socket
import sys

import httpx
import pytest
import sales_sql
import sql_agent
from sales_sql import SalesError, SalesTool, create_demo


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline test attempted network")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def tool(tmp_path):
    database = tmp_path / "sales.sqlite"
    create_demo(database)
    return SalesTool(database)


def response(content="完成", calls=None, reason=None):
    return {
        "finish_reason": reason or ("tool_calls" if calls else "stop"),
        "message": {"role": "assistant", "content": content, "tool_calls": calls},
    }


def tool_call(**params):
    return {
        "id": "call_sql",
        "type": "function",
        "function": {
            "name": "query_monthly_sales",
            "arguments": json.dumps(
                {**sql_agent.CASES["monthly"]["parameters"], **params}
            ),
        },
    }


class Chat:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.inputs = []
        self.requests = 4
        self.metadata = {"provider": "fake", "model": "scripted"}

    def __call__(self, messages, tools, *, tool_choice):
        self.requests += 1
        self.inputs.append((copy.deepcopy(messages), tools, tool_choice))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_real_sql_result_is_correlated_to_model_call(tool):
    chat = Chat(response(calls=[tool_call()]), response("虚构销售额3000.00元"))
    result = sql_agent.run_session("查询2026年9月销售额", chat, tool)
    assert (
        result["status"] == "completed"
        and result["stop_reason"] == "tool_result_returned"
    )
    assert result["model_requests"] == 2 and result["tool_executions"] == 1
    assert [item[2] for item in chat.inputs] == ["auto", "none"]
    trace = chat.inputs[1][0]
    assert [m["role"] for m in trace] == ["system", "user", "assistant", "tool"]
    assert trace[-1]["tool_call_id"] == trace[-2]["tool_calls"][0]["id"] == "call_sql"
    sql_result = json.loads(trace[-1]["content"])
    assert sql_result["total_cents"] == 300000 and sql_result["truncated"] is True
    assert (
        result["database_writes_by_tool"] is False
        and result["agent_checkpoint_saved"] is False
    )
    assert str(tool.database) not in json.dumps(chat.inputs, ensure_ascii=False)


@pytest.mark.parametrize(
    "case,amount,count",
    [
        ("monthly", 300000, 4),
        ("customer", 155000, 2),
        ("empty", 0, 0),
    ],
)
def test_offline_cases_execute_sql(tool, case, amount, count):
    result = sql_agent.run_session(
        sql_agent.CASES[case]["goal"], sql_agent.FixtureChat(case), tool
    )
    assert result["status"] == "completed" and result["model_requests"] == 0
    assert result["tool_executions"] == 1
    data = result["tool_results"][0]["result"]
    assert data["total_cents"] == amount and data["order_count"] == count


@pytest.mark.parametrize("goal", [None, {}, "", "  ", "x" * 2001])
def test_invalid_goal_stops_without_chat_or_sql(tool, goal):
    chat = Chat()
    result = sql_agent.run_session(goal, chat, tool)
    assert result["status"] == "rejected" and result["chat_turns"] == 0
    assert result["tool_attempts"] == 0 and chat.inputs == []


def test_clarification_does_not_open_a_missing_database(tmp_path):
    result = sql_agent.run_session(
        "查本月但未提供日期",
        Chat(response("请明确年份月份")),
        SalesTool(tmp_path / "missing.sqlite"),
    )
    assert result["status"] == "completed" and result["stop_reason"] == "direct_answer"
    assert result["tool_executions"] == 0


def test_multiple_calls_rejected_before_any_query(tool, monkeypatch):
    monkeypatch.setattr(
        tool, "query", lambda value: pytest.fail("Unexpected SQL query")
    )
    calls = [tool_call(), tool_call()]
    calls[1]["id"] = "call_second"
    result = sql_agent.run_session("query", Chat(response(calls=calls)), tool)
    assert (
        result["stop_reason"] == "multiple_tool_calls_not_supported"
        and result["tool_attempts"] == 0
    )


def test_second_round_call_rejected_without_second_query(tool):
    chat = Chat(response(calls=[tool_call()]), response(calls=[tool_call()]))
    result = sql_agent.run_session("query", chat, tool)
    assert (
        result["stop_reason"] == "tool_budget_exhausted"
        and result["tool_executions"] == 1
    )
    assert result["chat_turns"] == 2 and result["final_answer"] is None


@pytest.mark.parametrize(
    "parameters",
    [{"sql": "SELECT * FROM secrets"}, {"month": 13}, {"db": "other.sqlite"}],
)
def test_model_cannot_choose_sql_or_database(tool, monkeypatch, parameters):
    monkeypatch.setattr(tool, "query", lambda value: pytest.fail("Unexpected query"))
    result = sql_agent.run_session(
        "query", Chat(response(calls=[tool_call(**parameters)])), tool
    )
    assert result["status"] == "rejected" and result["tool_attempts"] == 0


@pytest.mark.parametrize(
    "code", ["database_missing", "query_budget_exceeded", "database_query_failed"]
)
def test_database_error_is_preserved_and_no_followup_model(tool, monkeypatch, code):
    def failed(params):
        raise SalesError(code)

    monkeypatch.setattr(tool, "query", failed)
    chat = Chat(response(calls=[tool_call()]))
    result = sql_agent.run_session("query", chat, tool)
    assert result["status"] == "rejected" and result["stop_reason"] == code
    assert result["tool_executions"] == 0 and result["model_requests"] == 1
    assert result["final_answer"] is None


def test_unexpected_tool_exception_never_leaks_database_path(tool, monkeypatch):
    def failed(params):
        raise RuntimeError("private/path secret-value")

    monkeypatch.setattr(tool, "query", failed)
    result = sql_agent.run_session("query", Chat(response(calls=[tool_call()])), tool)
    assert result["stop_reason"] == "tool_execution_failed"
    assert "secret-value" not in json.dumps(result)


@pytest.mark.parametrize("turn", [1, 2])
def test_model_timeout_has_no_retry(tool, turn):
    replies = [response(calls=[tool_call()])] if turn == 2 else []
    replies.append(sql_agent.ToolChatError("provider_timeout"))
    result = sql_agent.run_session("query", Chat(*replies), tool)
    assert result["stop_reason"] == "provider_timeout"
    assert result["model_requests"] == turn and result["tool_executions"] == turn - 1


def test_official_qwen_shape_round_trip_with_real_sql(tool):
    from types import SimpleNamespace

    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            call = tool_call()
            call["index"] = 0
            message = response(calls=[call])["message"]
            message["function_call"] = None
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "tool_calls", "message": message}]},
            )
        result = json.loads(body["messages"][-1]["content"])
        assert result["total_cents"] == 300000
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": response()["message"]}]
            },
        )

    chat = sql_agent.ChatTools(
        config_loader=lambda: SimpleNamespace(
            provider="qwen",
            model="fake",
            api_key="dummy",
            base_url="https://example.invalid/v1",
        ),
        transport=httpx.MockTransport(handler),
    )
    result = sql_agent.run_session("query", chat, tool)
    assert result["status"] == "completed" and len(seen) == 2
    assert seen[1]["tool_choice"] == "none"


@pytest.mark.parametrize("args", [[], ["--check-all"], ["--show-tools"]])
def test_offline_cli_never_loads_credentials(monkeypatch, capsys, args):
    monkeypatch.setattr(sys, "argv", ["sql_agent.py", *args])
    monkeypatch.setattr(
        sql_agent, "ChatTools", lambda *a: pytest.fail("Loaded real model")
    )
    assert sql_agent.main() == 0
    json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    "args", [["--live"], ["--env-file", "secret.env"], ["--live", "--check-all"]]
)
def test_cli_rejects_implicit_live_calls(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["sql_agent.py", *args])
    with pytest.raises(SystemExit) as error:
        sql_agent.main()
    assert error.value.code == 2


def test_sql_cli_init_then_query_and_refuse_overwrite(tmp_path, monkeypatch, capsys):
    path = tmp_path / "new.sqlite"
    monkeypatch.setattr(sys, "argv", ["sales_sql.py", "init-demo", "--db", str(path)])
    assert sales_sql.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "demo_created"
    assert sales_sql.main() == 1
    assert json.loads(capsys.readouterr().out)["error"] == "database_already_exists"
    monkeypatch.setattr(
        sys,
        "argv",
        ["sales_sql.py", "query", "--db", str(path), "--year", "2026", "--month", "9"],
    )
    assert sales_sql.main() == 0
    assert json.loads(capsys.readouterr().out)["total_cents"] == 300000
