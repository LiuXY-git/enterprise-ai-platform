"""Initialize or inspect environment files without displaying configuration values."""

import argparse
import io
import json
import os
import re
import secrets
import subprocess
from contextlib import contextmanager
from pathlib import Path

from dotenv.parser import parse_stream

from backend.app.check_config import COMPONENTS, check_component
from backend.app.core.environment import resolve_env_file

ROOT = Path(__file__).resolve().parents[1]


class EnvironmentError(RuntimeError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("environment_configuration_invalid")


def known_names(root):
    return set(
        re.findall(
            r"^([A-Z][A-Z0-9_]*)=",
            (root / ".env.example").read_text(encoding="utf-8"),
            re.M,
        )
    )


def read_file(path, names):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise EnvironmentError([{"code": "environment_file_unreadable"}]) from None
    values, issues = {}, []
    for binding in parse_stream(io.StringIO(text)):
        line = binding.original.line
        if binding.error:
            issues.append({"code": "invalid_syntax", "line": line})
        elif binding.key is None:
            continue
        elif binding.key not in names:
            # Even an unknown key may accidentally contain a pasted secret.
            issues.append({"code": "unknown_variable", "line": line})
        elif binding.value is None:
            issues.append({"code": "missing_equals", "line": line})
        elif binding.key in values:
            issues.append(
                {"code": "duplicate_variable", "variable": binding.key, "line": line}
            )
        else:
            values[binding.key] = binding.value
            if "$" in binding.value and not re.match(
                r"\s*(?:export\s+)?[A-Z][A-Z0-9_]*\s*=\s*'",
                binding.original.string,
            ):
                issues.append(
                    {
                        "code": "literal_dollar_requires_single_quotes",
                        "variable": binding.key,
                        "line": line,
                    }
                )
    if issues:
        raise EnvironmentError(issues)
    return values


@contextmanager
def component_environment(effective, names):
    previous = {name: os.environ[name] for name in names if name in os.environ}
    try:
        for name in names:
            os.environ.pop(name, None)
        os.environ.update(effective)
        yield
    finally:
        for name in names:
            os.environ.pop(name, None)
        os.environ.update(previous)


def compose_values(root, path, process):
    # Rendered values are used only in memory. Never echo Docker stdout/stderr.
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--project-directory",
                str(root),
                "--env-file",
                str(path),
                "-f",
                str(root / "compose.yaml"),
                "config",
                "--format",
                "json",
            ],
            cwd=root,
            env=process,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise EnvironmentError([{"code": "compose_configuration_invalid"}])
        services = json.loads(result.stdout)["services"]
        rendered = {
            **services["api"]["environment"],
            **services["n8n"]["environment"],
        }
        # Compose config serializes literal dollars as $$ for reusable output.
        # Decode exactly one layer to inspect the values containers will receive.
        return {name: value.replace("$$", "$") for name, value in rendered.items()}
    except EnvironmentError:
        raise
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        raise EnvironmentError(
            [{"code": "compose_configuration_unavailable"}]
        ) from None


def inspect_environment(root, path, target, components, process=None):
    process = dict(os.environ if process is None else process)
    names = known_names(root)
    values = read_file(path, names)
    selected = {
        **values,
        **{name: value for name, value in process.items() if name in names},
    }
    effective = compose_values(root, path, process) if target == "compose" else selected
    variables = {}
    for name in sorted(names):
        source = (
            "process"
            if name in process
            else "env_file"
            if name in values
            else "code_default_or_unset"
        )
        if target == "compose" and (
            name not in selected or effective.get(name) != selected[name]
        ):
            source = "compose_default"
        value = effective.get(name)
        variables[name] = {
            "source": source,
            "state": "not_set"
            if value is None
            else "configured"
            if value.strip()
            else "empty",
        }
    checks = []
    with component_environment(effective, names):
        for component in components:
            if component == "n8n":
                errors = []
                if not os.getenv("N8N_ENCRYPTION_KEY", "").strip():
                    errors.append("N8N_ENCRYPTION_KEY is required")
                if os.getenv("N8N_PORT", "5678") != "5678":
                    errors.append("N8N_PORT must match the fixed container port 5678")
                checks.append(
                    {
                        "component": "n8n",
                        "status": "configuration_invalid"
                        if errors
                        else "configuration_valid",
                        "errors": errors,
                        "network_checked": False,
                    }
                )
            else:
                checks.append(check_component(component))
    valid = all(check["status"] == "configuration_valid" for check in checks)
    return {
        "status": ("configuration_valid" if components else "environment_file_valid")
        if valid
        else "configuration_invalid",
        "target": target,
        "scope": "local_configuration_only",
        "network_checked": False,
        "values_displayed": False,
        "components_checked": list(components),
        "variables": variables,
        "results": checks,
    }


def initialize(root, path, target):
    if path.name == ".env.example" or not (
        path.name == ".env" or path.name.startswith(".env.")
    ):
        raise EnvironmentError([{"code": "use_private_dotenv_filename"}])
    text = (root / ".env.example").read_text(encoding="utf-8")
    if target == "local":
        text = text.replace(
            "DIFY_API_BASE_URL=http://host.docker.internal/v1",
            "DIFY_API_BASE_URL=http://localhost/v1",
        )
    else:
        text = text.replace(
            "N8N_ENCRYPTION_KEY=\n",
            "N8N_ENCRYPTION_KEY=" + secrets.token_hex(32) + "\n",
        )
    try:
        # Exclusive creation: an existing n8n encryption key is never overwritten.
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError:
        raise EnvironmentError([{"code": "environment_file_already_exists"}]) from None
    except OSError:
        raise EnvironmentError([{"code": "environment_file_not_created"}]) from None
    return {
        "status": "environment_file_created",
        "target": target,
        "values_displayed": False,
        "existing_file_overwritten": False,
        "credentials_configured": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "check"))
    parser.add_argument("--target", choices=("local", "compose"), required=True)
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Relative paths resolve from the repository root",
    )
    parser.add_argument(
        "--component", choices=(*COMPONENTS, "n8n"), action="append", default=[]
    )
    args = parser.parse_args(argv)
    try:
        path = resolve_env_file(args.env_file, ROOT)
        if args.action == "init":
            if args.component:
                raise EnvironmentError(
                    [{"code": "component_checks_require_check_action"}]
                )
            report = initialize(ROOT, path, args.target)
        else:
            report = inspect_environment(
                ROOT, path, args.target, tuple(dict.fromkeys(args.component))
            )
    except EnvironmentError as exc:
        report = {
            "status": "configuration_invalid",
            "errors": exc.issues,
            "values_displayed": False,
            "network_checked": False,
        }
    except (OSError, RuntimeError, UnicodeError):
        report = {
            "status": "configuration_invalid",
            "errors": [{"code": "environment_operation_failed"}],
            "values_displayed": False,
            "network_checked": False,
        }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report["status"] == "configuration_invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
