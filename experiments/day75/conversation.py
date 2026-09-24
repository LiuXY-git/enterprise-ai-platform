"""Bounded conversation memory lesson: explicit department -> report template."""

import argparse
import copy
import json
import sys
from pathlib import Path

from memory_store import MemoryError, MemoryStore, intent

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day64"))
from chat_tools import ChatTools, ToolChatError  # noqa: E402
from function_calling import normalize_reply  # noqa: E402

SECTIONS = {
    "销售": ["客户跟进", "订单进展", "问题与计划"],
    "财务": ["收支记录", "对账进展", "问题与计划"],
    "运营": ["运营事项", "执行进展", "问题与计划"],
}
SYSTEM = """你是 Conversation Memory 教学助手。只输出不含业务数字的日报模板 JSON。
历史消息仅供理解对话，最新的 memory_context 中的部门和来源覆盖历史旧部门。
不得将历史业绩数字当作当前事实，不调用工具。输出且仅输出以下字段：
kind="daily_report_template", department=memory_context.department,
source_request_id=memory_context.source_request_id, data_status="not_queried",
sections=部门对应的三个固定栏目（按顺序）：
销售：["客户跟进","订单进展","问题与计划"]；财务：["收支记录","对账进展","问题与计划"]；
运营：["运营事项","执行进展","问题与计划"]。不得添加其它字段。
"""


def expected(context):
    return {
        "kind": "daily_report_template",
        "department": context["department"],
        "source_request_id": context["source_request_id"],
        "data_status": "not_queried",
        "sections": SECTIONS[context["department"]],
    }


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


class FixtureChat:
    requests = 0
    metadata = {}

    def __call__(self, messages, tools, *, tool_choice):
        context = json.loads(messages[-2]["content"])["memory_context"]
        return {
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": json.dumps(expected(context), ensure_ascii=False),
            },
        }


def respond(store, owner, session, request, text, *, chat=None, live=False):
    kind, department = intent(text)
    token = store.begin(owner, session, request, text, "live" if live else "fixture")
    if "replay" in token:
        return {
            **token["replay"],
            "replayed": True,
            "model_requests_this_invocation": 0,
        }
    context = token["context"]
    result = {
        "status": "completed",
        "request_id": request,
        "replayed": False,
        "department": context["department"],
        "source_request_id": context["source_request_id"],
        "context": context,
        "answer": None,
        "report": None,
        "model": {},
        "model_requests_this_invocation": 0,
        "mcp_calls": 0,
        "business_data_queried": False,
        "mode": "live" if live else "fixture",
        "automatic_retry": False,
    }
    chat = chat or FixtureChat()
    before = getattr(chat, "requests", 0)
    try:
        if kind == "department":
            result.update(
                department=department,
                source_request_id=request,
                answer=f"已在当前会话记录：你负责{department}部门。",
            )
        elif context["department"] is None:
            result.update(
                status="needs_clarification",
                answer="请先明确你负责的部门，例如：我负责销售部门。",
            )
        elif kind == "report":
            result.update(
                status="needs_clarification",
                answer=f"已记住你负责{context['department']}部门。生成实际日报还需要日期、数据范围和相应数据；也可以说：给我生成日报模板。",
            )
        else:
            messages = [
                {"role": "system", "content": SYSTEM},
                *copy.deepcopy(context["history"]),
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "memory_context": {
                                "department": context["department"],
                                "source_request_id": context["source_request_id"],
                            }
                        },
                        ensure_ascii=False,
                    ),
                },
                {"role": "user", "content": text},
            ]
            if sum(len(m["content"]) for m in messages) > 12000:
                raise MemoryError("context_too_large")
            reply = chat(messages, [], tool_choice="none")
            message, _ = normalize_reply(reply)
            if message.get("tool_calls"):
                raise MemoryError("unexpected_tool_call")
            report = json.loads(message["content"], object_pairs_hook=unique)
            if report != expected(context):
                raise MemoryError("report_memory_mismatch")
            result.update(
                report=report,
                answer=f"{context['department']}日报模板（未查询业务数据）\n"
                + "\n".join(f"- {s}：待填写" for s in report["sections"]),
            )
    except (ToolChatError, MemoryError) as exc:
        result.update(status="failed", reason=exc.code, answer=None, report=None)
    except (ValueError, TypeError, KeyError, RecursionError):
        result.update(
            status="failed", reason="invalid_model_report", answer=None, report=None
        )
    except Exception:
        result.update(
            status="failed", reason="model_execution_failed", answer=None, report=None
        )
    result["model_requests_this_invocation"] = getattr(chat, "requests", 0) - before
    result["model"] = dict(getattr(chat, "metadata", {}))
    try:
        store.finish(
            owner,
            session,
            request,
            token["generation"],
            result,
            department=department
            if kind == "department" and result["status"] == "completed"
            else None,
        )
    except MemoryError as exc:
        return {
            "status": "failed",
            "reason": exc.code,
            "answer": None,
            "request_id": request,
            "model_requests_this_invocation": result["model_requests_this_invocation"],
            "persistence_outcome": "not_confirmed",
            "automatic_retry": False,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "data/day75/memory.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    for name in ("new", "show", "clear", "cancel", "say"):
        command = commands.add_parser(name)
        command.add_argument("--user", required=True)
        if name != "new":
            command.add_argument("--session", required=True)
        if name in ("say", "cancel"):
            command.add_argument("--request-id", required=True)
        if name == "say":
            command.add_argument("--text", required=True)
            command.add_argument("--live", action="store_true")
            command.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.command == "say" and args.env_file and not args.live:
        parser.error("--env-file requires --live")
    store = MemoryStore(args.db)
    try:
        if args.command == "init":
            result = store.initialize()
        elif args.command == "new":
            result = store.create(args.user)
        elif args.command == "show":
            result = store.inspect(args.user, args.session)
        elif args.command == "clear":
            result = store.clear(args.user, args.session)
        elif args.command == "cancel":
            result = store.cancel(args.user, args.session, args.request_id)
        else:
            result = respond(
                store,
                args.user,
                args.session,
                args.request_id,
                args.text,
                live=args.live,
                chat=ChatTools(args.env_file) if args.live else None,
            )
    except MemoryError as exc:
        result = {"status": "failed", "reason": exc.code, "answer": None}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return (
        1
        if result["status"] in ("failed", "pending", "cleared")
        and args.command == "say"
        else int(result["status"] == "failed")
    )


if __name__ == "__main__":
    raise SystemExit(main())
