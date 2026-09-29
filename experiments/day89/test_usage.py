"""Offline response capture, retry coverage, decimal pricing and fixture boundaries."""

import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/day64"))
from chat_tools import ChatTools, ToolChatError  # noqa: E402

from experiments.day85.contracts import canonical_hash  # noqa: E402
from experiments.day86.dataset_tool import read_json  # noqa: E402
from experiments.day88.latency import TimedReport  # noqa: E402
from experiments.day89 import runner  # noqa: E402
from experiments.day89.reporting import MeteredReport, fixture_usage  # noqa: E402
from experiments.day89.transport import MAX_BYTES, UsageTransport  # noqa: E402
from experiments.day89.usage import (  # noqa: E402
    Attempt,
    Pricing,
    parse_usage,
    summarize,
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Real network forbidden in usage tests")

    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "getaddrinfo", fail)


def price():
    return Pricing(
        schema_version="day89-pricing-v1",
        price_id="illustration-v1",
        provider="demo",
        model="demo-model",
        currency="CNY",
        input_per_million="2",
        output_per_million="8",
        basis="user_supplied_flat_text_rates",
        effective_date="2026-09-29",
        source_note="Fictional arithmetic example; not provider pricing.",
        illustrative=True,
    )


def attempt(index=1, inputs=100, outputs=40):
    return Attempt(
        attempt_id=index,
        provider="demo",
        model="demo-model",
        origin="synthetic_response",
        outcome="response",
        http_status=200,
        **parse_usage(
            {
                "usage": dict(
                    prompt_tokens=inputs,
                    completion_tokens=outputs,
                    total_tokens=inputs + outputs,
                )
            }
        ),
    )


def payload():
    return dict(
        model="demo-model",
        usage=dict(prompt_tokens=100, completion_tokens=40, total_tokens=140),
        choices=[
            dict(
                finish_reason="stop",
                message=dict(role="assistant", content="private output not in ledger"),
            )
        ],
    )


def client(handler):
    transport = UsageTransport(
        httpx.MockTransport(handler),
        provider="demo",
        model="demo-model",
        origin="synthetic_response",
    )
    config = SimpleNamespace(
        provider="demo",
        model="demo-model",
        base_url="https://invalid.example/v1",
        api_key="test-secret-never-record",
    )
    return ChatTools(config_loader=lambda: config, transport=transport), transport


def test_capture_before_frozen_client_discards_usage():
    chat, meter = client(lambda request: httpx.Response(200, json=payload()))
    reply = chat([{"role": "user", "content": "private input"}], [])
    assert "usage" not in reply and reply["finish_reason"] == "stop"
    assert len(meter.attempts) == 1 and meter.attempts[0].input_tokens == 100
    serialized = json.dumps([a.model_dump() for a in meter.attempts])
    assert all(
        secret not in serialized
        for secret in [
            "private input",
            "private output",
            "test-secret-never-record",
            "Authorization",
        ]
    )
    assert summarize(meter.attempts, price())["estimated_cost"] == "0.00052"


class Chunks(httpx.SyncByteStream):
    def __init__(self, parts):
        self.parts = parts

    def __iter__(self):
        yield from self.parts


def test_stream_is_forwarded_and_captured_once():
    raw = json.dumps(payload()).encode()
    chat, meter = client(
        lambda request: httpx.Response(200, stream=Chunks([raw[:20], raw[20:]]))
    )
    chat([{"role": "user", "content": "demo"}], [])
    assert len(meter.attempts) == 1 and meter.attempts[0].total_tokens == 140
    meter.close()
    assert len(meter.attempts) == 1


def test_reported_usage_kept_when_agent_rejects_response():
    body = payload()
    body["choices"] = []
    chat, meter = client(lambda request: httpx.Response(200, json=body))
    with pytest.raises(ToolChatError):
        chat([], [])
    assert meter.attempts[0].usage_status == "reported"
    assert summarize(meter.attempts, price())["estimated_cost"] == "0.00052"


def test_timeout_then_retry_remains_partial_not_zero():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("private provider info")
        return httpx.Response(200, json=payload())

    chat, meter = client(handler)
    with pytest.raises(ToolChatError):
        chat([], [])
    chat([], [])
    result = summarize(meter.attempts, price())
    assert result["attempts"] == 2 and result["reported_attempts"] == 1
    assert result["input_tokens"] is None and result["known_input_tokens"] == 100
    assert (
        result["estimated_cost"] is None and result["known_estimated_cost"] == "0.00052"
    )
    assert [a.attempt_id for a in meter.attempts] == [1, 2]


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "negative",
        "bool",
        "float",
        "string",
        "mismatch",
        "null",
        "oversize_count",
    ],
)
def test_bad_or_absent_usage_never_estimated(change):
    body = payload()
    if change == "missing":
        body.pop("usage")
    elif change == "null":
        body["usage"] = None
    elif change == "mismatch":
        body["usage"]["total_tokens"] = 999
    else:
        body["usage"]["prompt_tokens"] = {
            "negative": -1,
            "bool": True,
            "float": 1.5,
            "string": "100",
            "oversize_count": 10**12,
        }[change]
    parsed = parse_usage(body)
    assert parsed["usage_status"] in {"missing", "invalid"}
    assert parsed["input_tokens"] is None and not parsed["flat_pricing_supported"]


@pytest.mark.parametrize(
    "detail",
    [
        {"prompt_tokens_details": {"cached_tokens": 25}},
        {"completion_tokens_details": {"reasoning_tokens": 2}},
        {"cache_read_input_tokens": 5},
    ],
)
def test_special_billing_keeps_tokens_but_blocks_flat_price(detail):
    body = payload()
    body["usage"].update(detail)
    a = attempt().model_dump()
    a.update(parse_usage(body))
    result = summarize([Attempt.model_validate(a)], price())
    assert result["total_tokens"] == 140 and result["estimated_cost"] is None
    assert result["cost_reasons"] == ["unsupported_billing_details"]


def test_price_identity_and_missing_price():
    assert summarize([attempt()])["estimated_cost"] is None
    p = price().model_copy(update={"model": "another-model"})
    assert summarize([attempt()], p)["cost_reasons"] == ["price_identity_mismatch"]


def test_response_identity_mismatch_blocks_pricing():
    body = payload()
    body["model"] = "other-model"
    chat, meter = client(lambda request: httpx.Response(200, json=body))
    chat([], [])
    assert summarize(meter.attempts, price())["estimated_cost"] is None


def test_decimal_cost_and_all_retry_attempts():
    result = summarize([attempt(), attempt(2, 50, 10)], price())
    assert result["input_tokens"] == 150 and result["output_tokens"] == 50
    assert result["estimated_cost"] == "0.00070"
    zero = summarize([attempt(inputs=0, outputs=0)], price())
    assert zero["total_tokens"] == 0 and zero["estimated_cost"] == "0"
    assert summarize([], price())["estimated_cost"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_per_million", "-1"),
        ("output_per_million", "NaN"),
        ("input_per_million", 2.0),
        ("effective_date", "2026-02-30"),
        ("currency", "unknown"),
    ],
)
def test_bad_price_configuration_rejected(field, value):
    value_dict = price().model_dump()
    value_dict[field] = value
    with pytest.raises(ValueError):
        Pricing.model_validate(value_dict)


@pytest.mark.parametrize("fault", ["duplicate", "gap", "mixed"])
def test_ledger_cannot_double_count_or_mix_sources(fault):
    items = [attempt(), attempt(2)]
    if fault == "duplicate":
        items[1] = attempt()
    elif fault == "gap":
        items[1] = attempt(3)
    else:
        items[1] = attempt(2).model_copy(update={"origin": "provider_response"})
    with pytest.raises(ValueError):
        summarize(items, price())


def test_oversized_or_incomplete_response_retains_no_fake_usage():
    chat, meter = client(
        lambda request: httpx.Response(200, stream=Chunks([b"x" * (MAX_BYTES + 1)]))
    )
    with pytest.raises(ToolChatError):
        chat([], [])
    assert (
        meter.attempts[0].usage_status == "missing"
        and meter.attempts[0].total_tokens is None
    )


def execution():
    return TimedReport.model_validate(
        read_json(ROOT / "docs/evidence/day88/execution.json")
    )


def test_fixture_cost_zero_tokens_not_measured():
    result = fixture_usage(execution())
    assert result["summary"]["fixture_cases"] == 12
    assert result["summary"]["provider_requests"] == 0
    assert result["summary"]["estimated_model_api_cost"] == "0"
    assert result["summary"]["input_tokens"] is None
    assert sum(r["model_attempts"] for r in result["rows"]) == 24


def test_unobserved_case_blocks_total_cost():
    ex = execution()
    ex.rows[0].observed = None
    ex.rows[0].execution_status = "error"
    result = fixture_usage(ex)
    assert result["summary"]["unknown_cases"] == 1
    assert result["summary"]["estimated_model_api_cost"] is None
    assert result["summary"]["known_model_api_cost"] == "0"


@pytest.mark.parametrize("field", ["usage", "execution_sha256", "pricing_sha256"])
def test_metering_snapshot_rejects_tampering(field):
    ex = execution()
    data = dict(
        schema_version="day89-usage-v1",
        report_kind="fixture_execution_with_explicit_usage_coverage",
        execution=ex.model_dump(),
        execution_sha256=canonical_hash(ex.model_dump()),
        pricing=None,
        pricing_sha256=None,
        usage=fixture_usage(ex),
        source_sha256_lf={},
    )
    assert MeteredReport.model_validate(data)
    if field == "usage":
        data["usage"]["summary"]["input_tokens"] = 0
    else:
        data[field] = "0" * 64
    with pytest.raises(ValueError):
        MeteredReport.model_validate(data)


def test_replay_persists_price_snapshot_and_will_not_overwrite(tmp_path):
    ledger = tmp_path / "input.json"
    prices = tmp_path / "price.json"
    ledger.write_text(json.dumps([attempt().model_dump()]), encoding="utf-8")
    prices.write_text(price().model_dump_json(), encoding="utf-8")
    report = runner.replay(ledger, prices, tmp_path / "result")
    assert (
        report["summary"]["origin"] == "synthetic_response"
        and report["summary"]["illustrative"] is True
    )
    assert report["pricing_sha256"] == canonical_hash(price().model_dump())
    with pytest.raises(FileExistsError):
        runner.replay(ledger, prices, tmp_path / "result")


def test_cli_invalid_price_sanitizes_input_and_does_not_run(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "price.json"
    path.write_text('{"secret":"dont-echo"}', encoding="utf-8")

    def forbidden(*a, **k):
        raise AssertionError("Invalid price must not run Agent")

    monkeypatch.setattr(runner.latency, "run", forbidden)
    assert (
        runner.main(
            ["run", "--prices", str(path), "--output-dir", str(tmp_path / "run")]
        )
        == 1
    )
    assert (
        not (tmp_path / "run").exists() and "dont-echo" not in capsys.readouterr().out
    )
