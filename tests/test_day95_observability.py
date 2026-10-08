"""HTTP correlation, log privacy and request/response preservation."""

import asyncio
import json
import logging
import re

import httpx
import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from backend.app import database, logging_config, observability, workflow_logging
from backend.app.application import create_app
from backend.app.core import lifecycle
from backend.app.core.request_logging import RequestLoggingMiddleware
from tests.test_day51_workflow_logging import start_body

SECRET = "PRIVATE_DAY95_TOKEN"


@pytest.fixture(autouse=True)
def logging_state(monkeypatch):
    names = [
        logging_config.LOGGER_NAME,
        workflow_logging.EVENT_LOGGER,
        "enterprise_ai_platform.http",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "httpx",
        "httpcore",
    ]
    originals = []
    for name in names:
        logger = logging.getLogger(name)
        originals.append(
            (
                logger,
                list(logger.handlers),
                logger.level,
                logger.propagate,
                logger.disabled,
            )
        )
        monkeypatch.setattr(logger, "handlers", [])
        logger.disabled = False
    for name in ("configure_logging", "load_environment", "init_database"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    yield
    for logger, handlers, level, propagate, disabled in originals:
        for handler in logger.handlers:
            if handler not in handlers:
                handler.close()
        logger.handlers = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled


@pytest.fixture
def captured():
    records, workflows = [], []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(observability.JsonFormatter().format(record)))

    class WorkflowCapture(logging.Handler):
        def emit(self, record):
            workflows.append(json.loads(record.getMessage()))

    logger = logging.getLogger(logging_config.LOGGER_NAME)
    logger.handlers = [Capture()]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    events = logging.getLogger(workflow_logging.EVENT_LOGGER)
    events.handlers = [WorkflowCapture()]
    events.setLevel(logging.INFO)
    events.propagate = False
    return records, workflows


def http_events(records):
    return [r for r in records if r["event"].startswith("http_request_")]


@pytest.mark.parametrize(
    "method,path,body,status",
    [
        ("GET", "/health", None, 200),
        ("POST", "/chat", {"message": SECRET}, 200),
        ("POST", "/chat", {}, 422),
        ("GET", "/" + SECRET, None, 404),
        ("POST", "/health", None, 405),
        ("POST", "/upload/", None, 307),
    ],
)
def test_response_contract_and_one_correlated_event(
    captured, method, path, body, status
):
    records, _ = captured
    with TestClient(create_app(), follow_redirects=False) as client:
        response = client.request(
            method,
            path + "?token=" + SECRET,
            json=body,
            headers={"Authorization": "Bearer " + SECRET, "X-Request-ID": SECRET},
        )
    request_id = response.headers["x-request-id"]
    assert response.status_code == status
    assert re.fullmatch("[a-f0-9]{32}", request_id)
    event = http_events(records)[0]
    assert len(http_events(records)) == 1
    assert event["request_id"] == request_id
    assert event["status_code"] == status and event["duration_ms"] >= 0
    assert event["response_complete"] is True
    assert event["level"] == ("WARNING" if status >= 400 else "INFO")
    assert SECRET not in json.dumps(records)
    assert observability.current_request_id() is None


@pytest.mark.parametrize("handled", [False, True])
def test_500_and_handled_failure_have_header_and_safe_event(captured, handled):
    records, _ = captured
    app = create_app()

    @app.get("/failure")
    def fail():
        if handled:
            raise HTTPException(503, detail="Unavailable")
        raise RuntimeError(SECRET)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/failure")
    event = http_events(records)[0]
    assert response.status_code == (503 if handled else 500)
    assert event["request_id"] == response.headers["x-request-id"]
    assert event["event"] == "http_request_failed" and event["level"] == "ERROR"
    assert event.get("error_type") == (None if handled else "RuntimeError")
    if not handled:
        assert response.text == "Internal Server Error"
    assert SECRET not in json.dumps(records)
    assert observability.current_request_id() is None


def test_errors_still_propagate_to_test_clients(captured):
    app = create_app()

    @app.get("/raises")
    def raises():
        raise ValueError("fixture")

    with TestClient(app) as client, pytest.raises(ValueError, match="fixture"):
        client.get("/raises")
    assert observability.current_request_id() is None


def test_background_failure_preserves_already_sent_response(captured):
    records, _ = captured
    app = create_app()

    def failure():
        raise RuntimeError(SECRET)

    @app.get("/background")
    def background(tasks: BackgroundTasks):
        tasks.add_task(failure)
        return {"accepted": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/background")
    assert response.status_code == 200 and response.json() == {"accepted": True}
    event = http_events(records)[0]
    assert event["status_code"] == 200 and event["response_complete"] is True
    assert (
        event["event"] == "http_request_failed"
        and event["error_type"] == "RuntimeError"
    )
    assert event["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("fails", [False, True])
def test_stream_completion_is_not_confused_with_start(captured, fails):
    records, _ = captured
    app = create_app()

    async def parts():
        yield b"first"
        if fails:
            raise RuntimeError(SECRET)
        yield b"second"

    @app.get("/stream")
    def stream():
        return StreamingResponse(parts())

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/stream")
    event = http_events(records)[0]
    assert event["status_code"] == 200
    assert event["response_complete"] is (not fails)
    assert event["request_id"] == response.headers["x-request-id"]
    assert SECRET not in json.dumps(records)
    if not fails:
        assert response.content == b"firstsecond"


def test_concurrent_requests_keep_separate_context_and_template_paths(captured):
    records, _ = captured
    app = create_app()
    logger = logging.getLogger(logging_config.LOGGER_NAME)

    async def run():
        ready = asyncio.Event()
        arrivals = 0

        @app.get("/parallel/{item}")
        async def parallel(item: str):
            nonlocal arrivals
            first = observability.current_request_id()
            arrivals += 1
            if arrivals == 2:
                ready.set()
            await ready.wait()
            logger.info("unregistered %s", SECRET)
            assert observability.current_request_id() == first
            return {"request_id": first}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                client.get("/parallel/" + SECRET), client.get("/parallel/other")
            )
        ids = {r.headers["x-request-id"] for r in responses}
        assert len(ids) == 2 and ids == {r.json()["request_id"] for r in responses}
        assert observability.current_request_id() is None
        return ids

    ids = asyncio.run(run())
    events = http_events(records)
    assert {e["request_id"] for e in events} == ids
    assert all(e["route"] == "/parallel/{item}" for e in events)
    assert {e["request_id"] for e in records if e["event"] == "application_log"} == ids
    assert SECRET not in json.dumps(records)


def test_workflow_threadpool_and_duplicate_requests_share_business_id_only(
    captured, tmp_path, monkeypatch
):
    records, workflows = captured
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "workflow.db")
    database.init_database()
    with TestClient(create_app()) as client:
        first = client.post("/workflow-runs/start", json=start_body())
        second = client.post("/workflow-runs/start", json=start_body())
    assert first.status_code == second.status_code == 200
    ids = [r.headers["x-request-id"] for r in (first, second)]
    assert ids[0] != ids[1]
    assert [w["request_id"] for w in workflows] == ids
    assert workflows[0]["run_id"] == workflows[1]["run_id"]
    assert workflows[1]["outcome"] == "duplicate"
    assert all(w["service"] == observability.SERVICE for w in workflows)
    assert [e["request_id"] for e in http_events(records)] == ids


def test_logging_failure_does_not_retry_or_change_operation(monkeypatch):
    app = create_app()
    calls = []

    @app.get("/operation")
    def operation():
        calls.append(1)
        return {"ok": True}

    def broken(*args, **kwargs):
        raise OSError(SECRET)

    monkeypatch.setattr(logging.getLogger("enterprise_ai_platform.http"), "log", broken)
    response = TestClient(app).get("/operation")
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert calls == [1] and re.fullmatch(
        "[a-f0-9]{32}", response.headers["x-request-id"]
    )
    assert observability.current_request_id() is None


def test_cancellation_resets_context_and_records_no_fictitious_response(captured):
    async def run():
        async def app(scope, receive, send):
            raise asyncio.CancelledError()

        async def unused(*args):
            raise AssertionError("must not send or receive")

        token = observability.request_id_context.set("a" * 32)
        try:
            with pytest.raises(asyncio.CancelledError):
                await RequestLoggingMiddleware(app)(
                    {"type": "http", "method": "GET"}, unused, unused
                )
            assert observability.current_request_id() == "a" * 32
        finally:
            observability.request_id_context.reset(token)

    asyncio.run(run())
    event = http_events(captured[0])[0]
    assert event["status_code"] is None and event["response_complete"] is False
    assert event["error_type"] == "CancelledError"


def test_non_http_scope_is_untouched(captured):
    scope = {"type": "websocket"}
    seen = []

    async def app(received_scope, receive, send):
        assert received_scope is scope
        seen.append(1)

    asyncio.run(RequestLoggingMiddleware(app)(scope, None, None))
    assert seen == [1] and "state" not in scope and not captured[0]


def test_custom_middleware_can_still_be_added(captured):
    app = create_app()

    @app.middleware("http")
    async def custom(request, call_next):
        response = await call_next(request)
        response.headers["X-Custom"] = "kept"
        response.headers["X-Request-ID"] = SECRET
        return response

    response = TestClient(app).get("/health")
    assert response.headers["x-custom"] == "kept"
    assert len(response.headers.get_list("x-request-id")) == 1
    assert response.headers["x-request-id"] != SECRET


@pytest.mark.parametrize("known_template", [False, True])
def test_formatter_drops_raw_arguments_exception_text_and_extra_payload(known_template):
    message = "收到上传请求：filename=%s, content_type=%s" if known_template else SECRET
    record = logging.LogRecord(
        "enterprise_ai_platform.upload",
        logging.ERROR,
        __file__,
        15,
        message,
        (SECRET, SECRET),
        (ValueError, ValueError(SECRET), None),
    )
    record.payload = {"password": SECRET}
    result = observability.JsonFormatter().format(record)
    assert SECRET not in result and "\n" not in result
    parsed = json.loads(result)
    assert parsed["error_type"] == "ValueError" and parsed["request_id"] is None
    assert parsed["event"] == (
        "upload_received" if known_template else "application_log"
    )


def test_formatter_never_stringifies_arbitrary_objects():
    class PrivateObject:
        def __str__(self):
            raise AssertionError(SECRET)

    record = logging.LogRecord(
        "enterprise_ai_platform", logging.INFO, __file__, 10, PrivateObject(), (), None
    )
    assert (
        json.loads(observability.JsonFormatter().format(record))["event"]
        == "application_log"
    )


def test_log_sink_failure_does_not_dump_record_arguments(tmp_path, monkeypatch, capsys):
    handler = observability.SafeRotatingFileHandler(
        tmp_path / "app.log", maxBytes=1, backupCount=1
    )
    handler.setFormatter(observability.JsonFormatter())

    def fail():
        raise PermissionError(SECRET)

    monkeypatch.setattr(handler, "doRollover", fail)
    handler.stream.write("existing log\n")
    handler.stream.flush()
    try:
        handler.emit(
            logging.LogRecord(
                "enterprise_ai_platform", logging.ERROR, __file__, 5, SECRET, (), None
            )
        )
    finally:
        handler.close()
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert json.loads(captured.err)["event"] == "log_sink_failed"


def test_server_and_client_transport_output_cannot_echo_secret_urls(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(logging_config, "LOG_DIRECTORY", tmp_path)
    monkeypatch.setattr(logging_config, "LOG_FILE", tmp_path / "app.log")
    logging_config.configure_logging()
    logging_config.configure_logging()
    for name in ("uvicorn.access", "httpx", "httpcore", "httpcore.connection"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.warning("https://private/?key=" + SECRET)
    try:
        raise ValueError(SECRET)
    except ValueError:
        logging.getLogger("uvicorn.error").exception(SECRET)
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert json.loads(captured.err)["error_type"] == "ValueError"
    logger = logging.getLogger("uvicorn")
    assert len(logger.handlers) == 1


@pytest.mark.parametrize("needs_kill", [False, True])
def test_verifier_cleans_up_failed_child_and_strips_private_environment(
    tmp_path, monkeypatch, needs_kill
):
    import subprocess

    from scripts import verify_logging

    actions = []

    class Child:
        def poll(self):
            return None

        def terminate(self):
            actions.append("terminate")

        def kill(self):
            actions.append("kill")

        def wait(self, timeout):
            if needs_kill and "kill" not in actions:
                raise subprocess.TimeoutExpired("fixture-child", timeout)
            actions.append("wait")

    def launch(command, **kwargs):
        assert "EAP_ENV_FILE" not in kwargs["env"]
        assert "DASHSCOPE_API_KEY" not in kwargs["env"]
        return Child()

    ticks = iter([0, 60])
    monkeypatch.setenv("EAP_ENV_FILE", str(tmp_path / "private.env"))
    monkeypatch.setenv("DASHSCOPE_API_KEY", SECRET)
    monkeypatch.setattr(verify_logging.subprocess, "Popen", launch)
    monkeypatch.setattr(verify_logging.time, "monotonic", lambda: next(ticks))
    with pytest.raises(RuntimeError, match="isolated_server_startup_failed"):
        verify_logging.verify(tmp_path)
    assert actions == (
        ["terminate", "kill", "wait"] if needs_kill else ["terminate", "wait"]
    )
    assert not (tmp_path / "result.json").exists()


def test_verifier_failure_does_not_claim_success_or_echo_details(
    tmp_path, monkeypatch, capsys
):
    from scripts import verify_logging

    def fail(folder):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(verify_logging, "verify", fail)
    assert verify_logging.main(["--output-root", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err
    assert json.loads(output.out)["status"] == "failed"
