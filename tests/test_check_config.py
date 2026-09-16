import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app import check_config

ROOT = Path(__file__).resolve().parents[1]


def test_component_check_reports_missing_secret_without_network(capsys):
    assert check_config.main(["--component", "llm"]) == 1
    data = json.loads(capsys.readouterr().out)
    result = data["results"][0]
    assert result["credentials"] == {"DEEPSEEK_API_KEY": "missing"}
    assert result["errors"] == ["未配置 DEEPSEEK_API_KEY"]
    assert result["network_checked"] is False


@pytest.mark.parametrize(
    "component", ["llm", "dify", "external-knowledge", "feishu", "wecom"]
)
def test_cli_runs_without_application_database_or_network_imports(tmp_path, component):
    env_file = tmp_path / "config.env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=SECRET_MARKER\nDIFY_WORKFLOW_API_KEY=SECRET_MARKER\n"
        "DIFY_EXTERNAL_KNOWLEDGE_API_KEY=SECRET_MARKER\n"
        "FEISHU_APP_ID=app-id\nFEISHU_APP_SECRET=SECRET_MARKER\n"
        "FEISHU_RECEIVE_ID=oc_test\nWECOM_CORP_ID=corp\nWECOM_AGENT_ID=1\n"
        "WECOM_APP_SECRET=SECRET_MARKER\nWECOM_TO_USER=member\n",
        encoding="utf-8",
    )
    code = """
import sys
def guard(event, args):
    if event == "import" and args[0].split(".")[0] in {
        "openai", "httpx", "sqlite3", "chromadb", "fastapi"
    }:
        raise AssertionError("Unexpected application dependency")
    if event in {"socket.connect", "socket.getaddrinfo", "sqlite3.connect"}:
        raise AssertionError("Unexpected external side effect")
sys.addaudithook(guard)
from backend.app.check_config import main
raise SystemExit(main(sys.argv[1:]))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            "--component",
            component,
            "--env-file",
            str(env_file),
        ],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "SECRET_MARKER" not in result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == "configuration_valid"
    if component in {"dify", "external-knowledge"}:
        assert data["results"][0]["model"] == "externally_managed"
        assert data["results"][0]["model_checked"] is False


def test_model_and_url_values_are_not_dumped(monkeypatch, capsys):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "SECRET_MARKER")
    monkeypatch.setenv("DEEPSEEK_MODEL", "SECRET_MARKER")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.com/SECRET_MARKER")
    assert check_config.main(["--component", "llm"]) == 0
    assert "SECRET_MARKER" not in capsys.readouterr().out
    monkeypatch.setenv("LLM_PROVIDER", "SECRET_MARKER")
    assert check_config.main(["--component", "llm"]) == 1
    assert "SECRET_MARKER" not in capsys.readouterr().out


def test_feishu_checks_both_groups_and_all_requires_every_component(capsys):
    assert check_config.main(["--component", "feishu"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert len(data["results"][0]["errors"]) == 2
    assert check_config.main(["--all"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert len(data["results"]) == 5


def test_unreadable_explicit_environment_reports_safe_error(tmp_path, capsys):
    path = tmp_path / "SECRET_MARKER.env"
    assert check_config.main(["--component", "llm", "--env-file", str(path)]) == 1
    output = capsys.readouterr().out
    assert "SECRET_MARKER" not in output
    assert json.loads(output)["status"] == "configuration_invalid"


@pytest.mark.parametrize(
    "args", [[], ["--component", "unknown"], ["--all", "--component", "llm"]]
)
def test_argument_errors_exit_two(args):
    with pytest.raises(SystemExit) as caught:
        check_config.main(args)
    assert caught.value.code == 2
