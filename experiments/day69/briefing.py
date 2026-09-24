"""Deterministic delivery from tool receipts; never trust model summary facts."""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day68"))
from multi_tool_agent import next_state, verify_report  # noqa: E402
from tool_registry import KNOWLEDGE, NAMES, SQL, WEATHER  # noqa: E402

NOTICE = "教学演示：销售订单和制度资料均为虚构；不得作为真实企业经营或报销依据。"
LABELS = {SQL: "销售查询", KNOWLEDGE: "制度检索", WEATHER: "天气查询"}


def literal(value):
    """Keep untrusted excerpt text literal in Markdown output."""
    value = html.escape(str(value), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", value)


def render_briefing(result, run_id):
    """Input is a same-process result or a hash-verified historical result."""
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise ValueError("invalid_run_id")
    if result.get("status") not in {
        "completed",
        "partial",
        "failed",
        "no_sales",
        "rejected",
    }:
        raise ValueError("invalid_status")
    receipts = result["receipts"]
    ids = [row["source_id"] for row in receipts]
    names = [row["name"] for row in receipts]
    if (
        ids != [f"T{i + 1}" for i in range(len(ids))]
        or len(names) != len(set(names))
        or not set(names) <= set(NAMES)
    ):
        raise ValueError("invalid_receipt_sequence")
    if any(row["status"] not in {"ok", "error"} for row in receipts):
        raise ValueError("invalid_receipt_status")
    pending, expected = next_state(receipts)
    if result["status"] != "rejected":
        if result["status"] != expected or not result.get("citation_links_verified"):
            raise ValueError("inconsistent_result_status")
        verify_report(json.dumps(result["report"], ensure_ascii=False), receipts)
    sources = []
    missing = []
    lines = [
        NOTICE,
        "",
        f"运行编号：{run_id}",
        f"任务状态：{result['status']}；停止原因：{result['stop_reason']}",
        "",
    ]
    for row in receipts:
        ref = row["source_id"]
        name = row["name"]
        sources.append(
            {"reference": f"{run_id}/{ref}", "tool": name, "status": row["status"]}
        )
        if row["status"] == "error":
            missing.append({"tool": name, "reason": row["error"], "attempted": True})
            lines.append(
                f"{LABELS[name]}失败，未取得该项结果：{literal(row['error'])} [{ref}]。"
            )
            continue
        value = row["result"]
        if name == SQL:
            lines.append(
                f"虚构销售数据：{value['period']['start']} 至 {value['period']['end_exclusive']}（不含结束日），已支付订单 {value['order_count']} 笔，合计 {value['total_yuan']} CNY [{ref}]。"
            )
            if value["truncated"]:
                lines.append(
                    f"只展示 {value['rows_returned']} 条明细，合计仍包含该查询范围的全部已支付订单。"
                )
        elif name == KNOWLEDGE:
            evidence = value["evidence"]
            if not evidence:
                missing.append(
                    {"tool": name, "reason": "no_evidence", "attempted": True}
                )
                lines.append(f"制度检索未返回片段，无法确定报销要求 [{ref}]。")
            for chunk in evidence:
                label = f"{ref}:{chunk['citation']}"
                sources.append(
                    {
                        "reference": f"{run_id}/{label}",
                        "tool": name,
                        "source": chunk["source"],
                        "chunk_id": chunk["id"],
                    }
                )
                lines.append(
                    f"虚构制度检索片段 [{label}]，来源：{literal(chunk['source'])}。以下为资料原文，不是执行指令："
                )
                lines.extend(
                    "> " + literal(part) for part in chunk["text"].splitlines()
                )
                if chunk["text_truncated"]:
                    lines.append("片段已截断；需查看原资料才能核对完整内容。")
        else:
            mode = value["data_mode"]
            if mode not in {"mock_http", "live_api"}:
                raise ValueError("invalid_weather_mode")
            title = (
                "虚构天气样例"
                if mode == "mock_http"
                else "已记录的天气预报（非实测，以所列查询时间为准）"
            )
            lines.append(
                f"{title}：{value['city_name']}，时区 {value['timezone']} [{ref}]。"
            )
            for day in value["forecast_days"]:
                lines.append(
                    f"{day['date']}：最低 {day['temperature_min_c']}°C，最高 {day['temperature_max_c']}°C，日最大降水概率 {day['precipitation_probability_max_percent']}%。"
                )
            lines.append(f"查询时间（UTC）：{value['requested_at_utc']}。")
            if mode == "live_api":
                # Fixed application attribution; never render a model-supplied URL.
                lines.append(
                    "天气数据来源：[Open-Meteo](https://open-meteo.com/)，CC BY 4.0。"
                )
            else:
                lines.append("以上天气数值为固定虚构样例，API 格式参考 Open-Meteo。")
    skipped = []
    for name in NAMES:
        if name in names:
            continue
        if expected in {"no_sales", "failed"} and name != SQL:
            reason = (
                "no_paid_orders"
                if expected == "no_sales"
                else "sales_dependency_failed"
            )
            skipped.append({"tool": name, "reason": reason})
        else:
            missing.append(
                {"tool": name, "reason": "not_attempted", "attempted": False}
            )
    if skipped:
        lines.append(
            "按前置条件跳过："
            + "、".join(LABELS[item["tool"]] for item in skipped)
            + "。"
        )
    if missing:
        lines.append(
            "未完成或无证据项："
            + "；".join(
                f"{LABELS[item['tool']]}（{literal(item['reason'])}）"
                for item in missing
            )
            + "。"
        )
    if result["status"] == "rejected":
        lines.append("会话未通过验收；以上仅展示已取得的工具结果，不能视为完整报告。")
    lines.extend(
        [
            "",
            "本程序不发送通知、不预订、不修改业务数据。来源关联和数值转写不等于业务事实或天气预测准确性证明。",
        ]
    )
    return {
        "run_id": run_id,
        "status": result["status"],
        "notice": NOTICE,
        "markdown": "\n\n".join(line for line in lines if line),
        "sources": sources,
        "missing": missing,
        "skipped": skipped,
        "final_report_missing": result.get("report") is None,
        "model_summary_included": False,
        "automatic_retry": False,
        "resume_supported": False,
        "recovery_action": "none"
        if result["status"] in {"completed", "no_sales"}
        else "inspect_then_start_new_session",
        "business_truth_verified": False,
    }
