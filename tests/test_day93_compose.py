"""Deployment failure controls and the browser-facing API contract."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from backend.app.application import create_app
from backend.app.routers import rag, upload
from backend.app.services.retrieval_service import RetrievedChunk
from tests.test_day53_deployment import run_script

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "api_only,without_n8n,services",
    [
        (False, False, {"api", "frontend", "n8n"}),
        (False, True, {"api", "frontend"}),
        (True, False, {"api"}),
    ],
)
def test_service_selection_and_proxy_verification(
    tmp_path, api_only, without_n8n, services
):
    result, calls, _ = run_script(tmp_path, api_only=api_only, without_n8n=without_n8n)
    assert result.returncode == 0, result.stdout + result.stderr
    up = next(call for call in calls if "up" in call)
    build = next(call for call in calls if "build" in call)
    assert {"api", "frontend", "n8n"}.intersection(up) == services
    assert {"api", "frontend"}.intersection(build) == services - {"n8n"}
    probes = [call for call in calls if call[0] == "exec"]
    assert any("http://frontend:8080/api/health" in call[-1] for call in probes) is (
        not api_only
    )
    assert any(call[-2:] == ["nginx", "-t"] for call in probes) is (not api_only)
    assert not any(
        {"down", "rm", "prune", "--volumes"}.intersection(call) for call in calls
    )


def test_conflicting_deployment_modes_stop_before_docker(tmp_path):
    result, calls, _ = run_script(tmp_path, api_only=True, without_n8n=True)
    assert result.returncode != 0
    assert not calls


@pytest.mark.parametrize("failure", ["test-frontend", "-t", "-c"])
def test_failed_frontend_or_http_probe_is_not_reported_as_success(tmp_path, failure):
    result, calls, _ = run_script(tmp_path, checker=True, fail=failure)
    assert result.returncode != 0
    assert "Deployment checks passed" not in result.stdout
    assert not any("up" in call or "build" in call for call in calls)


def test_compose_preserves_storage_and_local_only_ports():
    services = yaml.safe_load((ROOT / "compose.yaml").read_text())["services"]
    assert set(services) == {"api", "frontend", "n8n"}
    assert services["frontend"]["depends_on"]["api"]["condition"] == "service_healthy"
    assert services["frontend"]["read_only"] is True
    assert services["api"]["volumes"] == [
        "./data:/app/data",
        "./logs:/app/logs",
        "./data/chroma-cache:/home/app/.cache/chroma",
    ]
    assert services["n8n"]["volumes"] == ["n8n_data:/home/node/.n8n"]
    assert "environment" not in services["frontend"]
    for service in services.values():
        assert all(port.startswith("127.0.0.1:") for port in service["ports"])


def test_frontend_api_contract_with_real_routes_and_isolated_services(monkeypatch):
    # No lifespan, real DB, model download or network. Exercise the actual routes.
    monkeypatch.setattr(upload, "create_document", lambda **kwargs: 27)
    monkeypatch.setattr(upload, "update_document_status", lambda *args, **kwargs: None)
    monkeypatch.setattr(upload, "index_document_text", lambda **kwargs: 1)
    monkeypatch.setattr(
        rag,
        "search_chunks",
        lambda question, top_k: [
            RetrievedChunk(
                id="fixture-0",
                text="固定检索片段",
                source="fixture.md",
                chunk_index=0,
                distance=0.1,
            ),
        ],
    )
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    response = client.post(
        "/upload", files={"file": ("fixture.md", b"# Fixture", "text/markdown")}
    )
    assert response.status_code == 200, response.text
    assert response.json()["document_id"] == 27
    assert response.json()["status"] == "indexed"
    assert response.json()["chunk_count"] == 1
    result = client.post("/rag/query", json={"question": "流程", "top_k": 3})
    assert result.status_code == 200
    assert result.json()["results"][0]["source"] == "fixture.md"


def test_frontend_api_rejects_bad_inputs():
    client = TestClient(create_app())
    assert (
        client.post("/rag/query", json={"question": "", "top_k": 3}).status_code == 422
    )
    assert client.post("/upload", files={"file": ("bad.exe", b"x")}).status_code == 415


@pytest.mark.parametrize("recovers", [True, False])
def test_proxy_check_tolerates_dns_refresh_but_stops_on_persistent_failure(
    monkeypatch, recovers
):
    import io
    import time
    import urllib.error
    import urllib.request

    script = (ROOT / "scripts/check-deployment.ps1").read_text(encoding="utf-8")
    probe = script.split("$frontendProbe = @'\n", 1)[1].split("\n'@", 1)[0]
    attempts, sleeps = [], []

    def open_url(url, timeout):
        if url.endswith("/api/health"):
            attempts.append(url)
            if not recovers or len(attempts) <= 2:
                raise urllib.error.URLError("API DNS address is refreshing")
            return io.BytesIO(b'{"status":"ok"}')
        return io.BytesIO(b"KNOWLEDGE HUB")

    monkeypatch.setattr(urllib.request, "urlopen", open_url)
    monkeypatch.setattr(time, "sleep", sleeps.append)
    if recovers:
        exec(compile(probe, "frontend-probe", "exec"), {})
        assert len(attempts) == 3 and sleeps == [3, 3]
    else:
        with pytest.raises(urllib.error.URLError):
            exec(compile(probe, "frontend-probe", "exec"), {})
        assert len(attempts) == 6 and len(sleeps) == 5
