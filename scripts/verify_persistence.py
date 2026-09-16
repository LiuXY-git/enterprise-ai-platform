"""Build and recreate an isolated API; never operate on production containers."""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, *, env, capture=False):
    result = subprocess.run(
        arguments,
        env=env,
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def verify(work_dir: Path) -> dict:
    token = uuid4().hex
    project = "day53-check-" + token
    image = "enterprise-ai-platform:day53-check-" + token
    directory = work_dir.resolve() / project
    directory.mkdir(parents=True, exist_ok=False)
    names = set(
        re.findall(
            r"^([A-Z][A-Z0-9_]*)=",
            (ROOT / ".env.example").read_text(encoding="utf-8"),
            re.M,
        )
    )
    # Do not inherit application secrets or Compose overrides from the caller.
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in names and not key.startswith("COMPOSE_")
    }
    (directory / ".env").write_text(
        "N8N_ENCRYPTION_KEY=isolated-check-only\n", encoding="utf-8"
    )
    source = run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(directory / ".env"),
            "-f",
            str(ROOT / "compose.yaml"),
            "config",
            "--format",
            "json",
        ],
        env=env,
        capture=True,
    )
    api = json.loads(source)["services"]["api"]
    api["image"] = image
    api["container_name"] = project + "-api"
    api["ports"] = []
    api["environment"] = {}
    mapping = {
        "/app/data": directory / "data",
        "/app/logs": directory / "logs",
        "/home/app/.cache/chroma": directory / "data/chroma-cache",
    }
    for volume in api["volumes"]:
        location = mapping[volume["target"]]
        location.mkdir(parents=True, exist_ok=True)
        volume["source"] = str(location)
    compose_file = directory / "compose.yaml"
    compose_file.write_text(
        json.dumps({"name": project, "services": {"api": api}}), encoding="utf-8"
    )
    scripts = directory / "scripts"
    scripts.mkdir()
    for name in ("start.ps1", "check-deployment.ps1", "deployment-common.ps1"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        raise RuntimeError("PowerShell is required for this Windows deployment check")
    compose = [
        "docker",
        "compose",
        "--project-directory",
        str(directory),
        "-f",
        str(compose_file),
        "-p",
        project,
    ]
    started = False
    evidence = {"project": project, "production_changed": False, "result": "failed"}
    try:
        started = True
        run(
            [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(scripts / "start.ps1"),
                "-ApiOnly",
            ],
            env=env,
        )
        before_id = run(compose + ["ps", "-q", "api"], env=env, capture=True)
        seed = """
import json, urllib.request
body = {
    'event_id': 'EVENT', 'workflow_name': 'day53-persistence-check',
    'source': 'isolated-test', 'requester': 'test-user', 'report_date': '2026-09-16',
    'input_data': {'question': 'synthetic persistence check'},
    'n8n_execution_id': 'day53-EVENT'
}
request = urllib.request.Request('http://127.0.0.1:8000/workflow-runs/start',
    data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request, timeout=10) as response:
    print(json.load(response)['run_id'])
""".replace("EVENT", token)
        run_id = run(
            ["docker", "exec", before_id, "python", "-c", seed], env=env, capture=True
        )
        app_log = directory / "logs/app.log"
        events_log = directory / "logs/workflow-events.jsonl"
        app_before = app_log.read_bytes()
        event_before = events_log.read_bytes()
        assert app_before and token.encode() in event_before
        run(
            compose
            + [
                "up",
                "-d",
                "--no-build",
                "--no-deps",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "120",
                "api",
            ],
            env=env,
        )
        after_id = run(compose + ["ps", "-q", "api"], env=env, capture=True)
        assert before_id != after_id, "Container was not recreated"
        probe = """
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8000/workflow-runs/RUN', timeout=10) as response:
    saved = json.load(response)
    assert saved['event_id'] == 'EVENT'
print('persisted')
""".replace("RUN", run_id).replace("EVENT", token)
        assert (
            run(
                ["docker", "exec", after_id, "python", "-c", probe],
                env=env,
                capture=True,
            )
            == "persisted"
        )
        assert app_log.read_bytes().startswith(app_before)
        assert events_log.read_bytes().startswith(event_before)
        run(
            [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(scripts / "check-deployment.ps1"),
                "-ApiOnly",
            ],
            env=env,
        )
        log_config = json.loads(
            run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .HostConfig.LogConfig}}",
                    after_id,
                ],
                env=env,
                capture=True,
            )
        )
        assert log_config == {
            "Type": "json-file",
            "Config": {"max-size": "10m", "max-file": "3"},
        }
        evidence.update(
            {
                "result": "passed",
                "container_recreated": True,
                "sqlite_record_preserved": True,
                "app_log_preserved": True,
                "workflow_events_preserved": True,
                "docker_log_limits": log_config,
                "start_script": "passed",
                "check_script": "passed",
                "n8n_recreation_tested": False,
            }
        )
        return evidence
    finally:
        if started:
            try:
                run(compose + ["down", "--timeout", "10"], env=env)
                # This tag is unique to this invocation, never the production tag.
                run(["docker", "image", "rm", image], env=env)
                evidence["isolated_resources_removed"] = True
            except subprocess.CalledProcessError:
                evidence["isolated_resources_removed"] = False
        (directory / "result.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        print("Evidence: " + str(directory / "result.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir", type=Path, default=ROOT / "logs/deployment-checks"
    )
    args = parser.parse_args()
    verify(args.work_dir)
