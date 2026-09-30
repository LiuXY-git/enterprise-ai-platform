"""Protect API compatibility and startup boundaries during application refactoring."""

import json
import socket
import sqlite3
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from backend.app import database
from backend.app.application import create_app
from backend.app.core import lifecycle
from backend.app.main import app


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original_connect = socket.socket.connect

    def local_connect(sock, address):
        # Windows asyncio creates a loopback socket pair for its event loop.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        raise AssertionError("Day 92 tests must not access external services")

    def blocked(*args, **kwargs):
        raise AssertionError("Day 92 tests must not access external services")

    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def test_public_openapi_matches_pre_refactor_snapshot():
    before = json.loads(
        (Path(__file__).parent / "fixtures/day92-openapi.json").read_text(
            encoding="utf-8"
        )
    )
    assert app.openapi() == before
    assert create_app().openapi() == before


def test_creating_application_does_not_start_resources(monkeypatch):
    def unexpected():
        raise AssertionError("resource started during construction")

    for name in ("init_database", "configure_logging", "load_environment"):
        monkeypatch.setattr(lifecycle, name, unexpected)
    first, second = create_app(), create_app()
    assert first is not second and first.openapi() == second.openapi()


def test_instances_do_not_share_overrides_or_metadata(monkeypatch):
    for name in ("load_environment", "configure_logging", "init_database"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    first, second = create_app(), create_app()

    def original():
        return "original"

    @first.get("/override-test")
    def route(value: Annotated[str, Depends(original)]):
        return {"value": value}

    first.dependency_overrides[original] = lambda: "override"
    first.state.marker = "first"
    first.openapi_tags[0]["description"] = "modified only in first"
    with TestClient(first) as client:
        assert client.get("/override-test").json() == {"value": "override"}
    assert not second.dependency_overrides and not hasattr(second.state, "marker")
    assert second.openapi_tags[0]["description"] != "modified only in first"
    assert "/override-test" not in second.openapi()["paths"]


def test_lifecycle_order_and_cache_cleanup(monkeypatch):
    calls = []
    for name in ("load_environment", "configure_logging", "init_database"):
        monkeypatch.setattr(lifecycle, name, lambda n=name: calls.append(n))
    instance = create_app()
    instance.state.wecom_cache = object()
    with TestClient(instance) as client:
        assert calls == ["load_environment", "configure_logging", "init_database"]
        assert instance.state.wecom_cache is None
        assert client.get("/health").json() == {"status": "ok"}
        instance.state.wecom_cache = object()
    assert instance.state.wecom_cache is None


def test_database_startup_failure_is_not_hidden(monkeypatch):
    monkeypatch.setattr(lifecycle, "load_environment", lambda: None)
    monkeypatch.setattr(lifecycle, "configure_logging", lambda: None)

    def fail():
        raise RuntimeError("fixture database unavailable")

    monkeypatch.setattr(lifecycle, "init_database", fail)
    with (
        pytest.raises(RuntimeError, match="fixture database unavailable"),
        TestClient(create_app()),
    ):
        pytest.fail("application must not accept requests after failed startup")


def test_shutdown_runs_when_request_raises(monkeypatch):
    for name in ("load_environment", "configure_logging", "init_database"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    instance = create_app()

    @instance.get("/failure-test")
    def fail():
        raise RuntimeError("fixture request error")

    with (
        pytest.raises(RuntimeError, match="fixture request error"),
        TestClient(instance) as client,
    ):
        instance.state.wecom_cache = object()
        client.get("/failure-test")
    assert instance.state.wecom_cache is None


def test_lifespan_initializes_only_isolated_sqlite(monkeypatch, tmp_path):
    path = tmp_path / "data/test.sqlite"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    monkeypatch.setattr(lifecycle, "configure_logging", lambda: None)
    for _ in range(2):
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"documents", "workflow_runs", "customers", "followup_records"} <= tables


def test_existing_http_entrypoints_and_chat_behavior(monkeypatch):
    for name in ("load_environment", "configure_logging", "init_database"):
        monkeypatch.setattr(lifecycle, name, lambda: None)
    with TestClient(create_app()) as client:
        for path in ("/health", "/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 200
        assert client.post("/chat", json={"message": "hello"}).json() == {
            "reply": "You said: hello"
        }
        assert client.post("/chat", json={}).status_code == 422
