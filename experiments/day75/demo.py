"""Run each conversation action in a separate process against a temporary DB."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def demonstrate(*, live=False, env_file=None):
    steps = []
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory(prefix="day75-memory-") as directory:
        database = Path(directory) / "demo.sqlite"

        def run(label, expected_status, *arguments):
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(Path(__file__).with_name("conversation.py")),
                    "--db",
                    str(database),
                    *arguments,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=90,
            )
            try:
                result = json.loads(completed.stdout)
            except ValueError:
                result = {"status": "failed", "reason": "non_json_child_output"}
            expected_exit = (
                1
                if expected_status in ("failed", "cleared") and arguments[0] != "clear"
                else 0
            )
            steps.append(
                {
                    "step": label,
                    "separate_process": True,
                    "exit_code": completed.returncode,
                    "passed": result.get("status") == expected_status
                    and completed.returncode == expected_exit,
                    "result": result,
                }
            )
            return result

        run("initialize", "initialized", "init")
        created = run("create_session", "created", "new", "--user", "demo-user")
        session = created.get("session_id", "missing")
        common = ["--user", "demo-user", "--session", session]
        run(
            "remember_sales",
            "completed",
            "say",
            *common,
            "--request-id",
            "fact-sales",
            "--text",
            "我负责销售部门",
        )
        model_args = ["--live"] if live else []
        if env_file:
            model_args += ["--env-file", str(env_file)]
        sales = [
            "say",
            *common,
            "--request-id",
            "template-sales",
            "--text",
            "给我生成日报模板",
            *model_args,
        ]
        first = run("restart_and_recall_sales", "completed", *sales)
        run("same_request_replay", "completed", *sales)
        run("show_saved_history", "available", "show", *common)
        other = run("create_other_session", "created", "new", "--user", "demo-user")
        run(
            "new_session_empty",
            "needs_clarification",
            "say",
            "--user",
            "demo-user",
            "--session",
            other.get("session_id", "missing"),
            "--request-id",
            "no-fact",
            "--text",
            "给我生成日报模板",
        )
        run(
            "other_user_denied",
            "failed",
            "show",
            "--user",
            "another-user",
            "--session",
            session,
        )
        run(
            "update_finance",
            "completed",
            "say",
            *common,
            "--request-id",
            "fact-finance",
            "--text",
            "改为财务部门",
        )
        second = run(
            "restart_and_recall_finance",
            "completed",
            "say",
            *common,
            "--request-id",
            "template-finance",
            "--text",
            "给我生成日报模板",
            *model_args,
        )
        run("clear_session", "cleared", "clear", *common)
        run("cleared_request_not_replayed", "cleared", *sales)
        last = run(
            "after_clear_needs_department",
            "needs_clarification",
            "say",
            *common,
            "--request-id",
            "after-clear",
            "--text",
            "给我生成日报模板",
        )
    facts_verified = (
        (first.get("report") or {}).get("department") == "销售"
        and (second.get("report") or {}).get("department") == "财务"
        and last.get("context", {}).get("department") is None
    )
    return {
        "passed": all(step["passed"] for step in steps) and facts_verified,
        "mode": "live" if live else "fixture",
        "fictional_user": True,
        "new_model_requests": sum(
            step["result"].get("model_requests_this_invocation", 0) for step in steps
        ),
        "mcp_calls": 0,
        "temporary_database": True,
        "steps": steps,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.env_file and not args.live:
        parser.error("--env-file requires --live")
    result = demonstrate(live=args.live, env_file=args.env_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
