"""Storage faults remain task failures; evaluator files use server-owned storage."""

import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from backend.app.console.config import ConsoleConfig
from backend.app.console.worker import Worker
from backend.app.console.workflow_task import payload
from backend.app.console.workflows import TEMPLATES, LeadInput


def test_sales_payload_matches_actual_n8n_allowlist():
    template = json.loads(
        (
            Path(__file__).resolve().parents[1] / "n8n/console/sales-followup.json"
        ).read_text(encoding="utf-8")
    )
    validator = next(
        n["parameters"]["jsCode"]
        for n in template["nodes"]
        if "allowedFields = new Set" in n.get("parameters", {}).get("jsCode", "")
    )
    allowlist = set(
        re.findall(r"'([^']+)'", validator.split("new Set([", 1)[1].split("]);", 1)[0])
    )
    fields = TEMPLATES["sales-followup"]["example"]
    request = payload(
        {
            "job_id": "a" * 32,
            "input": {"template_id": "sales-followup", "fields": fields},
        }
    )
    assert set(request) <= allowlist
    assert request["replay"] is False and request["event_id"] == "web-" + "a" * 32


@pytest.mark.parametrize(
    "change",
    [
        {"purchase_window_days": 366},
        {"sales_owner": "张 三"},
        {"customer_id": "bad/id"},
    ],
)
def test_sales_rejects_values_disallowed_by_upstream(change):
    with pytest.raises(ValueError):
        LeadInput.model_validate({**TEMPLATES["sales-followup"]["example"], **change})


def test_native_evaluation_path_loaded_from_server_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_CONSOLE_DATA_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("WEB_CONSOLE_EVALUATION_DATA_DIR", str(tmp_path / "native"))
    config = ConsoleConfig.from_environment()
    assert config.data_dir == tmp_path / "queue"
    assert config.evaluation_data_dir == tmp_path / "native"


@pytest.mark.skipif(sys.platform != "linux", reason="Run in Linux worker image")
@pytest.mark.parametrize(
    "fault", ["directory_exists", "process_failed", "timeout", "stop"]
)
def test_extended_worker_fault_keeps_safe_terminal_state(tmp_path, monkeypatch, fault):
    from backend.app.console import extended_worker

    stop = threading.Event()
    config = ConsoleConfig(
        tmp_path / "queue",
        evaluation_data_dir=tmp_path / "native",
        evaluation_timeout_seconds=5,
    )
    worker = Worker(config, stop=stop)
    worker.store.initialize()
    job, _ = worker.store.submit(
        {"kind": "evaluation", "mode": "fixture", "input": {"suite": "full"}}, "one"
    )
    worker.store.acquire(worker.owner, 15)
    worker.store.claim(worker.owner)
    if fault == "directory_exists":
        (config.evaluation_data_dir / job["job_id"]).mkdir(parents=True)
    else:
        real = subprocess.Popen

        def start(*_, **kwargs):
            if fault == "stop":
                stop.set()
            return real(
                [
                    sys.executable,
                    "-c",
                    'import sys; sys.stderr.write("PRIVATE_TRACE"); sys.exit(2)'
                    if fault == "process_failed"
                    else "import time; time.sleep(30)",
                ],
                **kwargs,
            )

        monkeypatch.setattr(extended_worker.subprocess, "Popen", start)
    worker.execute(job)
    result = worker.store.get(job["job_id"])
    assert result["status"] == ("interrupted" if fault == "stop" else "failed")
    assert "PRIVATE_TRACE" not in json.dumps(result)
    assert result["result"] is None
    assert not (config.data_dir / "runs" / job["job_id"]).exists()
    assert (config.evaluation_data_dir / job["job_id"]).exists()
    assert worker.store.worker_status()["status"] == "healthy"
    worker.store.release(worker.owner)
