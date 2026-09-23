"""Offline transport tests; no sockets, credentials or model requests are used."""

import json
import socket
from types import SimpleNamespace

import httpx
import pytest
from chat_tools import MAX_RESPONSE_BYTES, ChatTools, ToolChatError
from function_calling import CASES, run_session

MESSAGES = [{"role": "user", "content": "Use the fictional example tool."}]
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fictional_lookup",
            "description": "Read a fictional local record.",
            "parameters": {
                "type": "object",
                "properties": {"record_id": {"type": "string"}},
                "required": ["record_id"],
                "additionalProperties": False,
            },
        },
    }
]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Offline test attempted a real network request")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def config(provider="qwen"):
    return SimpleNamespace(
        provider=provider,
        model="fictional-test-model",
        api_key="private-test-key",
        base_url="https://provider.invalid/v1/",
    )


def payload(message=None, finish_reason="stop"):
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": "Fictional result."}
                if message is None
                else message,
            }
        ]
    }


def adapter_for(response):
    return ChatTools(
        config_loader=config,
        transport=httpx.MockTransport(lambda request: response),
    )


def assert_error(adapter, code, *, requests=1):
    with pytest.raises(ToolChatError) as exc:
        adapter(MESSAGES, TOOLS)
    assert exc.value.code == code
    assert str(exc.value) == code
    assert "private-test-key" not in str(exc.value)
    assert adapter.requests == requests


@pytest.mark.parametrize("provider", ["qwen", "deepseek"])
@pytest.mark.parametrize("tool_choice", ["auto", "none"])
def test_request_protocol_limits_and_metadata(provider, tool_choice):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=payload())

    adapter = ChatTools(
        config_loader=lambda: config(provider), transport=httpx.MockTransport(handler)
    )
    assert adapter.requests == 0 and adapter.metadata == {}
    result = adapter(MESSAGES, TOOLS, tool_choice=tool_choice)
    assert result == {
        "message": {"role": "assistant", "content": "Fictional result."},
        "finish_reason": "stop",
    }
    assert len(seen) == adapter.requests == 1
    assert adapter.metadata == {"provider": provider, "model": "fictional-test-model"}
    body = json.loads(seen[0].content)
    assert body["messages"] == MESSAGES and body["tools"] == TOOLS
    assert body["tool_choice"] == tool_choice
    assert body["max_tokens"] == 1600 and body["stream"] is False
    assert body["model"] == "fictional-test-model"
    assert "response_format" not in body
    assert "functions" not in body and "function_call" not in body
    assert str(seen[0].url) == "https://provider.invalid/v1/chat/completions"
    assert seen[0].headers["Authorization"] == "Bearer private-test-key"
    assert seen[0].extensions["timeout"] == {
        "connect": 10.0,
        "read": 30.0,
        "write": 30.0,
        "pool": 30.0,
    }
    if provider == "qwen":
        assert body["enable_thinking"] is False
    else:
        assert "enable_thinking" not in body


def test_no_tools_omits_tools_and_tool_choice():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=payload())

    adapter = ChatTools(config_loader=config, transport=httpx.MockTransport(handler))
    adapter(MESSAGES, [], tool_choice="none")
    assert "tools" not in bodies[0] and "tool_choice" not in bodies[0]


def test_tool_response_keeps_protocol_only():
    tool_calls = [
        {
            "id": "call-example-1",
            "type": "function",
            "function": {
                "name": "fictional_lookup",
                "arguments": '{"record_id":"example-1"}',
            },
        }
    ]
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": tool_calls,
        "reasoning_content": "Do not return this provider-specific field.",
        "provider_extra": "private-test-key",
    }
    adapter = adapter_for(
        httpx.Response(200, json=payload(message, finish_reason="tool_calls"))
    )
    result = adapter(MESSAGES, TOOLS)
    assert result == {
        "message": {"role": "assistant", "content": None, "tool_calls": tool_calls},
        "finish_reason": "tool_calls",
    }
    assert "private-test-key" not in json.dumps(result)


@pytest.mark.parametrize("status", [301, 302, 307, 401, 429, 500])
def test_http_errors_are_not_followed_retried_or_leaked(status):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            status,
            text="private-test-key provider internal error",
            headers={"location": "https://redirect.invalid"},
        )

    adapter = ChatTools(config_loader=config, transport=httpx.MockTransport(handler))
    assert_error(adapter, f"provider_http_{status}")
    assert len(seen) == 1


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ConnectTimeout, "provider_timeout"),
        (httpx.ReadTimeout, "provider_timeout"),
        (httpx.ConnectError, "provider_network_error"),
        (httpx.RemoteProtocolError, "provider_network_error"),
    ],
)
def test_network_errors_are_not_retried_or_leaked(exception, code):
    attempts = []

    def handler(request):
        attempts.append(request)
        raise exception("private-test-key provider detail", request=request)

    adapter = ChatTools(config_loader=config, transport=httpx.MockTransport(handler))
    assert_error(adapter, code)
    assert len(attempts) == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "private-test-key",
        {},
        {"choices": []},
        {"choices": {}},
        {"choices": [None]},
        {"choices": [[], {}]},
        {"choices": [{}, {}]},
        payload([]),
        payload({}),
        payload({"role": "user", "content": "private-test-key"}),
    ],
)
def test_invalid_envelope_is_rejected(value):
    adapter = adapter_for(httpx.Response(200, content=json.dumps(value)))
    assert_error(adapter, "provider_invalid_response")


@pytest.mark.parametrize("finish_reason", [None, "length", "content_filter", "error"])
def test_incomplete_response_is_rejected(finish_reason):
    adapter = adapter_for(
        httpx.Response(200, json=payload(finish_reason=finish_reason))
    )
    assert_error(adapter, "provider_incomplete_response")


@pytest.mark.parametrize("function_call", [{}, {"name": "fictional_lookup"}])
def test_legacy_function_call_is_rejected_even_if_empty(function_call):
    adapter = adapter_for(
        httpx.Response(
            200,
            json=payload(
                {"role": "assistant", "content": None, "function_call": function_call}
            ),
        )
    )
    assert_error(adapter, "legacy_function_call")


@pytest.mark.parametrize(
    "body,code",
    [
        (b"private-test-key is not JSON", "provider_invalid_response"),
        (b"\xff", "provider_invalid_response"),
        (b"x" * (MAX_RESPONSE_BYTES + 1), "response_too_large"),
    ],
    ids=["invalid-json", "invalid-encoding", "oversized"],
)
def test_byte_limit_and_invalid_json(body, code):
    assert_error(adapter_for(httpx.Response(200, content=body)), code)


def test_limit_applies_to_cumulative_decoded_stream():
    class Chunks(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * (MAX_RESPONSE_BYTES // 2)
            yield b"x" * (MAX_RESPONSE_BYTES // 2)
            yield b"x"

    assert_error(
        adapter_for(httpx.Response(200, stream=Chunks())), "response_too_large"
    )


def test_bad_configuration_is_lazy_and_makes_zero_requests():
    loaded = []

    def bad_config():
        loaded.append(True)
        raise RuntimeError("private-test-key configuration error")

    adapter = ChatTools(config_loader=bad_config)
    assert loaded == [] and adapter.requests == 0 and adapter.metadata == {}
    assert_error(adapter, "configuration_invalid", requests=0)
    assert loaded == [True]


def test_invalid_tool_choice_stops_before_loading_configuration():
    adapter = ChatTools(config_loader=lambda: pytest.fail("Loaded configuration"))
    with pytest.raises(ToolChatError, match="^invalid_tool_choice$"):
        adapter(MESSAGES, TOOLS, tool_choice="required")
    assert adapter.requests == 0


def test_request_counter_accumulates_across_explicit_calls():
    def handler(request):
        return httpx.Response(200, json=payload())

    adapter = ChatTools(config_loader=config, transport=httpx.MockTransport(handler))
    adapter(MESSAGES, TOOLS)
    adapter(MESSAGES, TOOLS, tool_choice="none")
    assert adapter.requests == 2


def official_shape_call(index=0):
    return {
        "id": "call_official_shape",
        "index": index,
        "type": "function",
        "function": {
            "name": "calculate_order_total",
            "arguments": json.dumps(
                {"unit_price_cents": 19900, "quantity": 3, "discount_percent": 10}
            ),
        },
    }


def official_shape_message(call):
    # Mirrors the documented non-streaming envelope, using a fictional tool.
    return {
        "role": "assistant",
        "content": "",
        "refusal": None,
        "audio": None,
        "function_call": None,
        "tool_calls": [call],
    }


def test_official_qwen_shape_completes_transport_and_core_round_trip():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(
                200,
                json=payload(
                    official_shape_message(official_shape_call()), "tool_calls"
                ),
            )
        assert len(bodies) == 2
        assert body["tool_choice"] == "none"
        call = body["messages"][-2]["tool_calls"][0]
        tool_message = body["messages"][-1]
        assert set(call) == {"id", "type", "function"}
        assert tool_message["role"] == "tool"
        assert tool_message["tool_call_id"] == call["id"] == "call_official_shape"
        assert json.loads(tool_message["content"])["total_yuan"] == "537.30"
        return httpx.Response(
            200,
            json=payload(
                {
                    "role": "assistant",
                    "content": "虚构订单优惠后金额为537.30元。",
                    "function_call": None,
                    "tool_calls": None,
                }
            ),
        )

    adapter = ChatTools(config_loader=config, transport=httpx.MockTransport(handler))
    result = run_session(CASES["quote"], adapter, mode="live")
    assert result["status"] == "completed"
    assert result["stop_reason"] == "tool_result_returned"
    assert result["chat_turns"] == result["model_requests"] == 2
    assert result["tool_attempts"] == result["tool_executions"] == 1
    assert result["tool_results"][0]["result"]["total_yuan"] == "537.30"
    assert "537.30" in result["final_answer"]
    assert result["external_business_actions"] is False
    assert "private-test-key" not in json.dumps(result)


@pytest.mark.parametrize("index", [0, 3])
def test_valid_position_metadata_is_removed_without_changing_call(index):
    call = official_shape_call(index)
    adapter = adapter_for(
        httpx.Response(200, json=payload(official_shape_message(call), "tool_calls"))
    )
    result = adapter(MESSAGES, TOOLS)
    normalized_call = result["message"]["tool_calls"][0]
    assert normalized_call == {
        key: value for key, value in call.items() if key != "index"
    }
    assert call["index"] == index


@pytest.mark.parametrize("index", [-1, False, True, 0.0, "0", None, {}, []])
def test_invalid_position_metadata_is_rejected_before_execution(index):
    adapter = adapter_for(
        httpx.Response(
            200,
            json=payload(
                official_shape_message(official_shape_call(index)), "tool_calls"
            ),
        )
    )
    result = run_session(CASES["quote"], adapter, mode="live")
    assert result["stop_reason"] == "provider_invalid_response"
    assert result["tool_attempts"] == result["tool_executions"] == 0
    assert result["model_requests"] == 1
    assert result["final_answer"] is None


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda call: call.update(extra="private-test-key"), "invalid_tool_call"),
        (
            lambda call: call["function"].update(extra="private-test-key"),
            "invalid_tool_call",
        ),
        (
            lambda call: call["function"].update(name="unknown_function"),
            "invalid_tool_call",
        ),
        (
            lambda call: call["function"].update(
                arguments=json.dumps(
                    {
                        "unit_price_cents": 19900,
                        "quantity": 3,
                        "discount_percent": 10,
                        "extra": "private-test-key",
                    }
                )
            ),
            "invalid_tool_arguments",
        ),
    ],
    ids=["call-extra", "function-extra", "unknown-name", "arguments-extra"],
)
def test_only_position_metadata_is_removed_before_strict_core_validation(
    mutation, code
):
    call = official_shape_call()
    mutation(call)
    adapter = adapter_for(
        httpx.Response(200, json=payload(official_shape_message(call), "tool_calls"))
    )
    result = run_session(CASES["quote"], adapter, mode="live")
    assert result["stop_reason"] == code
    assert result["tool_executions"] == 0 and result["model_requests"] == 1
    assert result["final_answer"] is None
    assert "private-test-key" not in json.dumps(result)
