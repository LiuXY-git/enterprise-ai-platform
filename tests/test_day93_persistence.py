"""Check isolation of the real Docker runner without starting Docker."""

import json
import os
import re
from pathlib import Path

import pytest

from scripts import verify_persistence as runner


@pytest.mark.parametrize("with_frontend", [False, True])
def test_isolated_runner_never_inherits_real_data_ports_or_credentials(
    tmp_path, monkeypatch, with_frontend
):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "must-not-inherit")
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "must-not-inherit")
    calls = []
    ids = iter(["before-api", "after-api"])
    isolated = None
    source = {
        "services": {
            "api": {
                "volumes": [
                    {"target": "/app/data", "source": "REAL_DATA"},
                    {"target": "/app/logs", "source": "REAL_LOGS"},
                    {"target": "/home/app/.cache/chroma", "source": "REAL_CACHE"},
                ]
            },
            "frontend": {"ports": ["127.0.0.1:8080:8080"]},
        }
    }

    def run(arguments, *, env, capture=False):
        nonlocal isolated
        assert "DASHSCOPE_API_KEY" not in env
        assert "COMPOSE_PROJECT_NAME" not in env
        calls.append(arguments)
        if "config" in arguments:
            isolated = Path(arguments[arguments.index("--env-file") + 1]).parent
            return json.dumps(source)
        if "ps" in arguments:
            return next(ids)
        if "inspect" in arguments:
            return json.dumps(
                {"Type": "json-file", "Config": {"max-size": "10m", "max-file": "3"}}
            )
        if arguments[0:2] == ["docker", "exec"]:
            probe = arguments[-1]
            if "workflow-runs/start" in probe:
                token = re.search(r"'event_id': '([^']+)'", probe)[1]
                (isolated / "logs/app.log").write_text("fixture-log")
                (isolated / "logs/workflow-events.jsonl").write_text(token)
                return "fixture-run"
            if "print('persisted')" in probe:
                return "persisted"
        return ""

    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(runner.shutil, "which", lambda name: "powershell")
    result = runner.verify(tmp_path, with_frontend=with_frontend)
    config = json.loads((isolated / "compose.yaml").read_text())
    assert config["name"].startswith("day53-check-")
    api = config["services"]["api"]
    assert api["ports"] == [] and api["environment"] == {}
    assert all(Path(v["source"]).is_relative_to(isolated) for v in api["volumes"])
    assert ("frontend" in config["services"]) is with_frontend
    if with_frontend:
        assert config["services"]["frontend"]["ports"] == []
        assert any("collection.add" in c[-1] for c in calls)
        assert any("collection.query" in c[-1] for c in calls)
    assert result["chroma_recreation_tested"] is with_frontend
    assert result["result"] == "passed" and result["isolated_resources_removed"]
    down = next(c for c in calls if "down" in c)
    assert down[down.index("-p") + 1] == config["name"]
    assert "--volumes" not in down
    assert not any("prune" in c for c in calls)
    assert os.environ["DASHSCOPE_API_KEY"] == "must-not-inherit"
