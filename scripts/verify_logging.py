"""Verify API logs using synthetic requests and a temporary loopback server."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_MARKER = "DAY95_SYNTHETIC_PRIVATE_VALUE"


def worker(folder):
    import socket

    import uvicorn
    from fastapi import BackgroundTasks

    from backend.app import database, logging_config, settings
    from backend.app.application import create_app

    # Never read the operator's .env or use their SQLite/log directories.
    settings.DEFAULT_ENV_FILE = folder / "unused.env"
    database.DATABASE_PATH = folder / "database.sqlite"
    logging_config.LOG_DIRECTORY = folder
    logging_config.LOG_FILE = folder / "app.log"
    app = create_app()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=0, access_log=True, log_level="info"
    )
    server = uvicorn.Server(config)

    @app.get("/fixture-error", include_in_schema=False)
    def failure():
        raise RuntimeError(PRIVATE_MARKER)

    @app.get("/fixture-background", include_in_schema=False)
    def background(tasks: BackgroundTasks):
        tasks.add_task(failure)
        return {"accepted": True}

    @app.get("/fixture-stop", include_in_schema=False)
    def stop():
        server.should_exit = True
        return {"stopping": True}

    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        (folder / "ready.json").write_text(
            json.dumps({"port": sock.getsockname()[1]}), encoding="utf-8"
        )
        server.run(sockets=[sock])
    finally:
        sock.close()


def read_records(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify(folder):
    import urllib.error
    import urllib.request

    # Preserve only infrastructure settings, remove platform selectors/secrets.
    prefixes = (
        "EAP_",
        "LLM_",
        "DEEPSEEK_",
        "DASHSCOPE_",
        "QWEN_",
        "DIFY_",
        "FEISHU_",
        "WECOM_",
        "N8N_",
        "COMPOSE_",
    )
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(prefixes)}
    env.update(
        PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", ANONYMIZED_TELEMETRY="False"
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request_ids = []

    with (folder / "server-console.log").open("w", encoding="utf-8") as console:
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "--worker",
                str(folder),
            ],
            cwd=ROOT,
            env=env,
            stdout=console,
            stderr=console,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 45
            ready = folder / "ready.json"
            while not ready.exists():
                if child.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("isolated_server_startup_failed")
                time.sleep(0.1)
            # Reading a partially written readiness file is avoided by retrying.
            while True:
                try:
                    port = json.loads(ready.read_text(encoding="utf-8"))["port"]
                    break
                except (ValueError, KeyError):
                    if time.monotonic() > deadline:
                        raise RuntimeError(
                            "isolated_server_readiness_invalid"
                        ) from None
                    time.sleep(0.05)
            base = f"http://127.0.0.1:{port}"

            def request(path, expected, body=None):
                data = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(
                    base + path + "?token=" + PRIVATE_MARKER,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + PRIVATE_MARKER,
                        "X-Request-ID": PRIVATE_MARKER,
                    },
                )
                try:
                    response = opener.open(req, timeout=5)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    if response.status != expected:
                        raise RuntimeError("unexpected_fixture_response")
                    request_id = response.headers.get("X-Request-ID", "")
                    if not re.fullmatch("[a-f0-9]{32}", request_id):
                        raise RuntimeError("missing_request_id")
                    request_ids.append(request_id)
                    raw = response.read()
                    return json.loads(raw) if expected == 200 else None

            while True:
                try:
                    request("/health", 200)
                    break
                except (OSError, RuntimeError):
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("isolated_server_health_failed") from None
                    time.sleep(0.1)
            request("/chat", 200, {"message": PRIVATE_MARKER})
            request("/chat", 422, {})
            request("/" + PRIVATE_MARKER, 404)
            request("/fixture-error", 500)
            request("/fixture-background", 200)
            body = {
                "event_id": "day95-fixture",
                "workflow_name": "log-fixture",
                "source": "fixture",
                "requester": "synthetic-user",
                "report_date": "2026-10-08",
                "n8n_execution_id": "day95-fixture",
                "input_data": {
                    "question": "synthetic input",
                    "api_key": PRIVATE_MARKER,
                },
            }
            first = request("/workflow-runs/start", 200, body)
            second = request("/workflow-runs/start", 200, body)
            assert first["run_id"] == second["run_id"]
            request("/fixture-stop", 200)
            child.wait(timeout=10)
            if child.returncode:
                raise RuntimeError("isolated_server_shutdown_failed")
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)

    records = read_records(folder / "app.log")
    workflows = read_records(folder / "workflow-events.jsonl")
    requests = [r for r in records if r["event"].startswith("http_request_")]
    assert len(requests) == len(request_ids) == len(set(request_ids)) == 9
    assert {r["request_id"] for r in requests} == set(request_ids)
    error = next(r for r in requests if r["route"] == "/fixture-error")
    assert error["status_code"] == 500 and error["error_type"] == "RuntimeError"
    background = next(r for r in requests if r["route"] == "/fixture-background")
    assert (
        background["status_code"] == 200
        and background["event"] == "http_request_failed"
    )
    assert background["response_complete"] is True
    assert [w["request_id"] for w in workflows] == request_ids[-3:-1]
    assert workflows[1]["outcome"] == "duplicate"
    assert all(r["duration_ms"] >= 0 for r in requests)
    for name in ("app.log", "workflow-events.jsonl", "server-console.log"):
        assert PRIVATE_MARKER not in (folder / name).read_text(encoding="utf-8")
    result = {
        "status": "passed",
        "timestamp": datetime.now(UTC).isoformat(),
        "http_requests": len(requests),
        "workflow_events": len(workflows),
        "checks": [
            "response_header_correlation",
            "unique_server_generated_ids",
            "validation_and_unmatched_routes",
            "unhandled_500",
            "background_error_preserves_sent_status",
            "workflow_duplicate_correlation",
            "nonnegative_monotonic_duration",
            "private_marker_absent_from_all_sinks",
        ],
        "real_model_requests": 0,
        "notification_sends": 0,
        "existing_environment_files_read": False,
        "existing_data_or_containers_changed": False,
        "server": "temporary_loopback_uvicorn",
        "server_stopped": True,
    }
    (folder / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path, default=ROOT / "logs/logging-checks"
    )
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        worker(args.worker.resolve())
        return 0
    folder = args.output_root.resolve() / ("day95-" + uuid4().hex)
    folder.mkdir(parents=True, exist_ok=False)
    try:
        result = verify(folder)
    except Exception:
        # Raw transport/exception text can contain the synthetic marker.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": "logging_verification_failed",
                    "output_dir": str(folder),
                }
            )
        )
        return 1
    print(json.dumps({**result, "output_dir": str(folder)}))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
