"""Create, inspect and resume a persisted simulation of a Day 59 plan."""

import argparse
import json
from pathlib import Path

from task_store import ROOT, StoreError, TaskStore, read_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-dir", type=Path, default=ROOT / "data/day60")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Persist a plan and pause before S1")
    start.add_argument("--plan-file", type=Path)
    for name in ("status", "resume", "recover"):
        command = commands.add_parser(name)
        command.add_argument("--task-id", required=True)
        if name == "resume":
            command.add_argument("--checkpoint-id", required=True)
    args = parser.parse_args()
    store = TaskStore(args.store_dir)
    try:
        if args.command == "start":
            result = store.start(read_plan(args.plan_file))
        elif args.command == "resume":
            result = store.resume(args.task_id, args.checkpoint_id)
        else:
            result = getattr(store, args.command)(args.task_id)
    except StoreError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    except OSError:
        print(json.dumps({"status": "error", "error": "storage_io_error"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
