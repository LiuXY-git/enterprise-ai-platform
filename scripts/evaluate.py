"""Run the existing fixture evaluator using weekly evidence archives."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evidence_layout import workspace  # noqa: E402

PATH_OPTIONS = {"--output-dir", "--input-dir", "--report", "--dataset", "--agent"}
TEST_PATHS = {
    87: [
        "experiments/day85/test_framework.py",
        "experiments/day86/test_dataset.py",
        "experiments/day87/test_runner.py",
        "scripts/day84/test_v10_release.py",
    ],
    88: ["experiments/day88/test_latency.py"],
    89: ["experiments/day89/test_usage.py"],
    90: [
        "experiments/day64/test_chat_tools.py",
        *[f"experiments/day{d}" for d in range(85, 91)],
        "scripts/day84/test_v10_release.py",
        "scripts/day91/test_release.py",
    ],
}


def absolute_arguments(arguments, cwd):
    result = list(arguments)
    for index, value in enumerate(result):
        if value in PATH_OPTIONS and index + 1 < len(result):
            result[index + 1] = str((cwd / result[index + 1]).resolve())
        else:
            key, separator, path = value.partition("=")
            if separator and key in PATH_OPTIONS:
                result[index] = key + "=" + str((cwd / path).resolve())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--stage", choices=(87, 88, 89, 90), default=90, type=int)
    options, arguments = parser.parse_known_args(argv)
    arguments = absolute_arguments(arguments or ["--help"], Path.cwd())
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    try:
        with workspace(ROOT) as copied:
            command = (
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    *TEST_PATHS[options.stage],
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp=" + str(copied / "test-tmp"),
                    "--tb=short",
                    *arguments[1:],
                ]
                if arguments and arguments[0] == "test"
                else [
                    sys.executable,
                    "-B",
                    "-m",
                    f"experiments.day{options.stage}.runner",
                    *arguments,
                ]
            )
            return subprocess.run(
                command,
                cwd=copied,
                env=env,
                check=False,
            ).returncode
    except (OSError, ValueError, KeyError) as exc:
        print(f"Evaluation could not start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
