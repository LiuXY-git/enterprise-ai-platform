import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.app import logging_config, workflow_logging

ROOT = Path(__file__).resolve().parents[1]


def test_application_log_rotates_without_duplicate_handlers(tmp_path, monkeypatch):
    app_logger = logging.getLogger(logging_config.LOGGER_NAME)
    event_logger = logging.getLogger(workflow_logging.EVENT_LOGGER)
    originals = [
        (item, item.level, item.propagate) for item in (app_logger, event_logger)
    ]
    for logger, _, _ in originals:
        monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logging_config, "LOG_DIRECTORY", tmp_path)
    monkeypatch.setattr(logging_config, "LOG_FILE", tmp_path / "app.log")
    try:
        logging_config.configure_logging()
        handlers = list(app_logger.handlers)
        logging_config.configure_logging()
        assert app_logger.handlers == handlers
        handler = next(
            h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert handler.maxBytes == 5 * 1024 * 1024
        assert handler.backupCount == 3
        handler.maxBytes = 200
        for number in range(20):
            app_logger.info("rotation %s %s", number, "x" * 100)
        assert len(list(tmp_path.glob("app.log*"))) == 4
        assert "rotation 19" in (tmp_path / "app.log").read_text(encoding="utf-8")
    finally:
        for logger, level, propagate in originals:
            for handler in logger.handlers:
                handler.close()
            logger.setLevel(level)
            logger.propagate = propagate


MOCK_DOCKER = r"""
$ErrorActionPreference = 'Stop'
function docker {
    $a = @($args | ForEach-Object { [string]$_ })
    [IO.File]::AppendAllText($env:DAY53_TRACE, (ConvertTo-Json -Compress -InputObject $a) + "`n")
    $global:LASTEXITCODE = 0
    if ($a -contains $env:DAY53_FAIL -and $env:DAY53_FAIL -ne '') {
        $global:LASTEXITCODE = 1
        return
    }
    if ($a -contains 'version') { return '5.5.1' }
    if ($a[0] -eq 'info') { return '29.0.0' }
    if ($a -contains 'ps' -and $a -contains '-q') { return ('test-' + $a[-1]) }
    if ($a[0] -eq 'inspect') {
        if ($a[2] -like '*State.Status*') { return 'running healthy' }
        if ($a[2] -eq '{{.Config.User}}') {
            if ($a[-1] -eq 'test-frontend') { return 'nginx' }
            return 'app'
        }
        if ($a[2] -eq '{{json .Mounts}}') {
            if ($a[-1] -eq 'test-n8n') {
                return '[{"Type":"volume","Destination":"/home/node/.n8n","RW":true}]'
            }
            $dataPath = Join-Path $env:DAY53_ROOT 'data'
            if ($env:DAY53_FAIL -eq 'wrong-mount') { $dataPath = Join-Path $env:DAY53_ROOT 'wrong-data' }
            return ConvertTo-Json -Compress -InputObject @(
                @{Type='bind';Destination='/app/data';Source=$dataPath;RW=$true},
                @{Type='bind';Destination='/app/logs';Source=(Join-Path $env:DAY53_ROOT 'logs');RW=$true},
                @{Type='bind';Destination='/home/app/.cache/chroma';Source=(Join-Path $env:DAY53_ROOT 'data/chroma-cache');RW=$true}
            )
        }
    }
    if ($a -contains '-m') { return '{"status":"configuration_valid"}' }
}
"""


def run_script(
    tmp_path,
    *,
    fail="",
    api_only=False,
    checker=False,
    env_file=True,
    without_n8n=False,
):
    project = tmp_path / "project with spaces"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    for name in ("start.ps1", "check-deployment.ps1", "deployment-common.ps1"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    if env_file:
        (project / ".env").write_text(
            "N8N_ENCRYPTION_KEY=fake-test-key\n", encoding="utf-8"
        )
    trace = tmp_path / "trace.jsonl"
    env = {
        **os.environ,
        "DAY53_ROOT": str(project),
        "DAY53_TRACE": str(trace),
        "DAY53_FAIL": fail,
    }
    entry = "check-deployment.ps1" if checker else "start.ps1"
    wrapper = tmp_path / "invoke.ps1"
    wrapper.write_text(
        MOCK_DOCKER
        + f"\n& (Join-Path $env:DAY53_ROOT 'scripts/{entry}') "
        + ("-ApiOnly " if api_only else "")
        + ("-WithoutN8n " if without_n8n else "")
        + "-CheckComponents @('llm', 'dify')\n",
        encoding="utf-8-sig",
    )
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is required for the Windows deployment scripts")
    result = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    calls = (
        [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        if trace.exists()
        else []
    )
    return result, calls, project


@pytest.mark.parametrize("api_only", [False, True])
def test_start_builds_then_waits_and_verifies_from_any_directory(tmp_path, api_only):
    result, calls, project = run_script(tmp_path, api_only=api_only)
    assert result.returncode == 0, result.stdout + result.stderr
    build = next(i for i, call in enumerate(calls) if "build" in call)
    up = next(i for i, call in enumerate(calls) if "up" in call)
    assert build < up
    assert "--wait" in calls[up] and "--no-build" in calls[up]
    assert ("n8n" in calls[up]) is not api_only
    assert ("--no-deps" in calls[up]) is api_only
    for call in calls:
        assert not {"down", "prune", "rm", "--volumes"}.intersection(call)
        if call[0] == "compose" and "version" not in call:
            assert str(project) in call
            assert call[call.index("--ansi") + 1] == "never"
            assert call[call.index("--progress") + 1] == "plain"
        if "config" in call:
            assert "--quiet" in call
    probes = [call for call in calls if "-m" in call]
    assert [call[-1] for call in probes] == ["llm", "dify"]


@pytest.mark.parametrize("failure", ["config", "build", "up"])
def test_failed_deployment_stops_before_later_steps(tmp_path, failure):
    result, calls, _ = run_script(tmp_path, fail=failure)
    assert result.returncode != 0
    if failure == "config":
        assert not any("build" in call for call in calls)
    if failure in {"config", "build"}:
        assert not any("up" in call for call in calls)
    assert not any(call[0] == "exec" for call in calls)


def test_missing_env_stops_before_build(tmp_path):
    result, calls, _ = run_script(tmp_path, env_file=False)
    assert result.returncode != 0
    assert not any("build" in call or "up" in call for call in calls)


def test_checker_rejects_wrong_mount_without_mutating_services(tmp_path):
    result, calls, _ = run_script(tmp_path, checker=True, fail="wrong-mount")
    assert result.returncode != 0
    assert not any("up" in call or "build" in call for call in calls)
    assert not any(call[0] == "exec" for call in calls)
