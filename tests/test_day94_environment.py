"""Environment selection, redaction and credential-preservation controls."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import settings
from backend.app.core import environment
from scripts import manage_env as manager
from tests.test_day53_deployment import run_script

ROOT = Path(__file__).resolve().parents[1]
SECRET = "PRIVATE_TEST_MARKER"
DOLLAR = chr(36)


def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    shutil.copyfile(ROOT / ".env.example", root / ".env.example")
    return root


def test_explicit_api_file_does_not_fall_back_to_old_dotenv(tmp_path, monkeypatch):
    old = tmp_path / ".env"
    old.write_text("DEEPSEEK_API_KEY=" + SECRET + "\n")
    selected = tmp_path / ".env.selected"
    selected.write_text("LLM_PROVIDER=qwen\nDASHSCOPE_API_KEY=selected-key\n")
    monkeypatch.setattr(settings, "DEFAULT_ENV_FILE", old)
    monkeypatch.setenv("EAP_ENV_FILE", str(selected))
    monkeypatch.setenv("QWEN_MODEL", "process-model")
    environment.load_environment()
    assert "DEEPSEEK_API_KEY" not in os.environ
    assert os.environ["DASHSCOPE_API_KEY"] == "selected-key"
    assert os.environ["QWEN_MODEL"] == "process-model"


@pytest.mark.parametrize("value", ["", " ", "missing.env"])
def test_invalid_selected_file_fails_without_default_fallback(
    tmp_path, monkeypatch, value
):
    old = tmp_path / ".env"
    old.write_text("DEEPSEEK_API_KEY=" + SECRET + "\n")
    monkeypatch.setattr(settings, "DEFAULT_ENV_FILE", old)
    monkeypatch.setenv("EAP_ENV_FILE", value)
    with pytest.raises(RuntimeError):
        environment.load_environment()
    assert "DEEPSEEK_API_KEY" not in os.environ


def test_default_api_file_still_works_and_relative_path_is_repo_based(
    tmp_path, monkeypatch
):
    old = tmp_path / ".env"
    old.write_text("LLM_PROVIDER=qwen\n")
    monkeypatch.setattr(settings, "DEFAULT_ENV_FILE", old)
    monkeypatch.chdir(tmp_path)
    environment.load_environment()
    assert os.environ["LLM_PROVIDER"] == "qwen"
    assert (
        environment.resolve_env_file(".env.selected")
        == environment.PROJECT_ROOT / ".env.selected"
    )


@pytest.mark.parametrize("target", ["local", "compose"])
def test_init_uses_target_address_and_never_overwrites_existing(tmp_path, target):
    root = project(tmp_path)
    path = root / (".env." + target)
    result = manager.initialize(root, path, target)
    values = manager.read_file(path, manager.known_names(root))
    host = "localhost" if target == "local" else "host.docker.internal"
    assert values["DIFY_API_BASE_URL"] == f"http://{host}/v1"
    if target == "compose":
        assert re.fullmatch("[0-9a-f]{64}", values["N8N_ENCRYPTION_KEY"])
        assert values["N8N_ENCRYPTION_KEY"] not in json.dumps(result)
    else:
        assert values["N8N_ENCRYPTION_KEY"] == ""
    before = path.read_bytes()
    with pytest.raises(
        manager.EnvironmentError, match="environment_configuration_invalid"
    ):
        manager.initialize(root, path, target)
    assert path.read_bytes() == before


@pytest.mark.parametrize("name", [".env.example", "config.txt"])
def test_init_rejects_public_filenames(tmp_path, name):
    root = project(tmp_path)
    before = (root / ".env.example").read_bytes()
    with pytest.raises(manager.EnvironmentError):
        manager.initialize(root, root / name, "compose")
    assert (root / ".env.example").read_bytes() == before


@pytest.mark.parametrize(
    "content,code",
    [
        ("LEAKED_PRIVATE_TEST_MARKER=x\n", "unknown_variable"),
        ("DEEPSEEK_API_KEY\n", "missing_equals"),
        (
            "DEEPSEEK_API_KEY=x\nDEEPSEEK_API_KEY=PRIVATE_TEST_MARKER\n",
            "duplicate_variable",
        ),
        ("DEEPSEEK_API_KEY='PRIVATE_TEST_MARKER\n", "invalid_syntax"),
        (
            "DEEPSEEK_API_KEY=" + DOLLAR + "{PRIVATE_TEST_MARKER}\n",
            "literal_dollar_requires_single_quotes",
        ),
    ],
)
def test_malformed_files_emit_no_values_or_unknown_keys(
    tmp_path, monkeypatch, capsys, content, code
):
    root = project(tmp_path)
    path = root / ".env.bad"
    path.write_text(content)
    monkeypatch.setattr(manager, "ROOT", root)
    assert manager.main(["check", "--target", "local", "--env-file", path.name]) == 1
    output = capsys.readouterr()
    assert code in output.out
    assert SECRET not in output.out + output.err


def test_literal_secret_and_process_precedence_are_redacted_and_environment_restored(
    tmp_path, monkeypatch
):
    root = project(tmp_path)
    path = root / ".env.selected"
    path.write_text(
        "LLM_PROVIDER=qwen\nDASHSCOPE_API_KEY='"
        + SECRET
        + DOLLAR
        + "{literal}'\nQWEN_MODEL=file-model\n"
    )
    monkeypatch.setenv("QWEN_MODEL", "process-model")
    previous = dict(os.environ)
    report = manager.inspect_environment(root, path, "local", ("llm",))
    assert report["status"] == "configuration_valid"
    assert report["variables"]["QWEN_MODEL"]["source"] == "process"
    assert report["variables"]["DASHSCOPE_API_KEY"]["source"] == "env_file"
    assert SECRET not in json.dumps(report)
    assert "process-model" not in json.dumps(report)
    assert dict(os.environ) == previous
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    report = manager.inspect_environment(root, path, "local", ("llm",))
    assert report["status"] == "configuration_invalid"
    assert report["variables"]["DASHSCOPE_API_KEY"] == {
        "source": "process",
        "state": "empty",
    }


def test_check_without_components_does_not_claim_credential_validation(tmp_path):
    root = project(tmp_path)
    path = root / ".env"
    path.write_text("")
    report = manager.inspect_environment(root, path, "local", (), process={})
    assert report["status"] == "environment_file_valid"
    assert not report["components_checked"] and not report["results"]
    assert report["variables"]["DEEPSEEK_MODEL"]["source"] == "code_default_or_unset"


def test_compose_checks_actual_rendered_values_and_masks_output(tmp_path, monkeypatch):
    root = project(tmp_path)
    path = root / ".env"
    path.write_text("LLM_PROVIDER=qwen\nQWEN_MODEL=\nDASHSCOPE_API_KEY=file-key\n")
    effective = {
        "LLM_PROVIDER": "qwen",
        "QWEN_MODEL": "compose-default-model",
        "DASHSCOPE_API_KEY": SECRET,
        "N8N_ENCRYPTION_KEY": SECRET,
    }

    def render(args, **kwargs):
        assert args[args.index("--env-file") + 1] == str(path)
        assert kwargs["capture_output"] and kwargs["env"]["DASHSCOPE_API_KEY"] == SECRET
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "services": {
                        "api": {"environment": effective},
                        "n8n": {"environment": {}},
                    }
                }
            ),
        )

    monkeypatch.setattr(manager.subprocess, "run", render)
    report = manager.inspect_environment(
        root, path, "compose", ("llm", "n8n"), process={"DASHSCOPE_API_KEY": SECRET}
    )
    assert report["status"] == "configuration_valid"
    assert report["variables"]["QWEN_MODEL"]["source"] == "compose_default"
    assert report["variables"]["DASHSCOPE_API_KEY"]["source"] == "process"
    assert SECRET not in json.dumps(report)


def test_failed_compose_does_not_echo_docker_stderr(tmp_path, monkeypatch, capsys):
    root = project(tmp_path)
    path = root / ".env"
    path.write_text("")
    monkeypatch.setattr(manager, "ROOT", root)
    monkeypatch.setattr(
        manager.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout=SECRET, stderr=SECRET),
    )
    assert manager.main(["check", "--target", "compose"]) == 1
    output = capsys.readouterr()
    assert "compose_configuration_invalid" in output.out
    assert SECRET not in output.out + output.err


def test_n8n_fixed_port_is_validated(tmp_path):
    root = project(tmp_path)
    path = root / ".env"
    path.write_text("N8N_ENCRYPTION_KEY=x\nN8N_PORT=1234\n")
    result = manager.inspect_environment(root, path, "local", ("n8n",), process={})
    assert result["status"] == "configuration_invalid"


@pytest.mark.parametrize("checker", [False, True])
def test_powershell_passes_selected_file_to_every_compose_operation(tmp_path, checker):
    result, calls, root = run_script(
        tmp_path,
        checker=checker,
        selected_file=".env.review",
        env_argument=".env.review",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for call in calls:
        if call[0] == "compose" and "version" not in call:
            assert Path(call[call.index("--env-file") + 1]) == root / ".env.review"


def test_missing_selected_file_never_uses_default_dotenv(tmp_path):
    result, calls, _ = run_script(tmp_path, env_argument=".env.missing")
    assert result.returncode != 0
    assert not calls


def test_private_profiles_are_ignored_but_example_is_trackable(tmp_path):
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for filename in (".env", ".env.compose", ".env.production", "nested/.env.test"):
        checked = subprocess.run(
            ["git", "check-ignore", "--no-index", filename],
            cwd=tmp_path,
            capture_output=True,
        )
        assert checked.returncode == 0
    checked = subprocess.run(
        ["git", "check-ignore", "--no-index", ".env.example"],
        cwd=tmp_path,
        capture_output=True,
    )
    assert checked.returncode == 1


@pytest.mark.parametrize("literal", ["one$token", "two$$tokens", "three$$$tokens"])
def test_compose_serialization_decodes_one_dollar_layer(tmp_path, monkeypatch, literal):
    root = project(tmp_path)
    path = root / ".env"
    path.write_text("DEEPSEEK_API_KEY='" + literal + "'")
    rendered = literal.replace("$", "$$")
    monkeypatch.setattr(
        manager.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "services": {
                        "api": {"environment": {"DEEPSEEK_API_KEY": rendered}},
                        "n8n": {"environment": {}},
                    }
                }
            ),
        ),
    )
    effective = manager.compose_values(root, path, {})
    assert effective["DEEPSEEK_API_KEY"] == literal
    report = manager.inspect_environment(root, path, "compose", (), process={})
    assert report["variables"]["DEEPSEEK_API_KEY"]["source"] == "env_file"
    assert literal not in json.dumps(report)
