"""Independent deterministic grading for the fixed Day 86 fixture contract."""

import json
from collections import Counter
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from experiments.day85.contracts import (
    Identifier,
    Sha256,
    StrictContract,
    canonical_hash,
)
from experiments.day86.dataset_tool import (
    ROOT,
    read_json,
    reject_constant,
    unique_object,
)
from experiments.day89.reporting import MeteredReport


class Rule(StrictContract):
    rule_id: Identifier
    expected: Any
    actual: Any
    passed: bool

    @model_validator(mode="after")
    def truthful(self) -> Self:
        if self.passed != (
            canonical_hash(self.expected) == canonical_hash(self.actual)
        ):
            raise ValueError("rule_result_mismatch")
        return self


class Grade(StrictContract):
    case_id: Identifier
    category: str
    judgement: Literal["passed", "failed", "error", "not_evaluated"]
    reason: (
        Literal["execution_error", "evidence_invalid", "execution_incomplete"] | None
    ) = None
    checks: Annotated[list[Rule], Field(max_length=80)]
    failed_rules: list[Identifier]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        ids = [r.rule_id for r in self.checks]
        failed = [r.rule_id for r in self.checks if not r.passed]
        if len(ids) != len(set(ids)) or self.failed_rules != failed:
            raise ValueError("rule_inventory_mismatch")
        if self.judgement in {"passed", "failed"}:
            if (
                not self.checks
                or self.reason is not None
                or (self.judgement == "passed") != (not failed)
            ):
                raise ValueError("grade_mismatch")
        elif self.checks or self.reason is None:
            raise ValueError("ungraded_case_has_rules")
        if (self.judgement == "not_evaluated") != (
            self.reason == "execution_incomplete"
        ):
            raise ValueError("incomplete_reason_mismatch")
        return self


def summary(rows):
    counts = Counter(r.judgement for r in rows)
    total = len(rows)
    complete = total > 0 and counts["not_evaluated"] == 0
    return dict(
        selected=total,
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["error"],
        not_evaluated=counts["not_evaluated"],
        status="complete" if complete else "incomplete",
        numerator=counts["passed"],
        denominator=total,
        success_rate=round(counts["passed"] / total, 6) if complete else None,
        success_rate_percent=round(100 * counts["passed"] / total, 2)
        if complete
        else None,
    )


def summary_groups(rows):
    return {
        category: summary([r for r in rows if r.category == category])
        for category in sorted({r.category for r in rows})
    }


def expected_text(case, citation):
    """Manually specified acceptance template; never imports Agent renderer."""
    g = case.golden_report
    scope = g.scope
    money = f"{g.total_cents // 100}.{g.total_cents % 100:02d}"
    text = f"教学虚构数据：{scope.year}年{scope.month}月，{scope.customer_id or '所有客户'}。"
    if case.expected.business_status == "no_data":
        text += "该范围没有已支付订单，销售额为0.00元。"
    else:
        text += f"已支付订单{len(g.matched_order_ids)}条，销售额{money}元。"
        if g.truncated:
            text += f"仅展示{g.rows_returned}条明细，销售额仍为全量合计。"
    text += f"\n来源：{citation}（MCP只读查询回执）。"
    if case.behavior.degraded:
        text = "模型回答服务暂不可用，以下为已校验回执的本地模板结果。\n" + text
    return text


def judge(case, observed, trace, journal):
    checks = []

    def check(name, expected, actual):
        checks.append(
            Rule(
                rule_id=name,
                expected=expected,
                actual=actual,
                passed=canonical_hash(expected) == canonical_hash(actual),
            )
        )

    check("business_status", case.expected.business_status, observed.business_status)
    for key, value in case.behavior.model_dump().items():
        check("behavior_" + key, value, getattr(observed, key))
    check("scenario", case.input.scenario, trace["generation"].get("scenario"))
    check("fixture_prompt_profile", "candidate", trace["prompt"].get("profile"))
    check(
        "model_attempt_input_count",
        observed.model_attempts,
        len(trace["actual_model_inputs"]),
    )
    check("tool_dispatch_count", case.behavior.tool_attempts, observed.mcp_dispatches)
    check("event_count", observed.event_count, len(journal["events"]))
    check(
        "event_sequence",
        list(range(1, len(journal["events"]) + 1)),
        [e["seq"] for e in journal["events"]],
    )
    check("terminal_recorded", True, journal["terminal_recorded"])
    attempts = [
        e
        for e in journal["events"]
        if e["kind"] == "model_started" and e["payload"].get("phase") == "attempt"
    ]
    tools = [
        e
        for e in journal["events"]
        if e["kind"] == "tool_call" and e["payload"].get("phase") == "attempt"
    ]
    check("logged_model_attempts", case.behavior.model_attempts, len(attempts))
    check("logged_tool_attempts", case.behavior.tool_attempts, len(tools))
    retries = [
        e["payload"].get("stage")
        for e in journal["events"]
        if e["kind"] == "agent_decision"
        and e["payload"].get("phase") == "recovery"
        and e["payload"].get("action") == "retry"
    ]
    check("logged_model_retries", case.behavior.model_retries, retries.count("model"))
    check("logged_tool_retries", case.behavior.tool_retries, retries.count("tool"))
    receipt_messages = [
        m
        for turn in trace["actual_model_inputs"]
        for m in turn["messages"]
        if m.get("role") == "tool"
    ]
    receipts = [
        json.loads(
            m["content"],
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
        for m in receipt_messages
    ]
    citation = observed.agent_run_id + "/T1"
    # has_citation is about the final answer, not merely possession of a receipt.
    cited = (
        isinstance(observed.answer, str)
        and ("\n来源：" + citation + "（MCP只读查询回执）。") in observed.answer
    )
    actual = dict(
        approval_status=observed.approval_status,
        simulated_effects=observed.simulated_effects,
        external_send=observed.external_send,
        has_citation=cited,
    )
    if case.golden_report:
        check("receipt_present", True, bool(receipts))
        g = case.golden_report
        if receipts:
            first = receipts[0]
            check(
                "receipt_consistency",
                True,
                all(canonical_hash(r) == canonical_hash(first) for r in receipts),
            )
            check("receipt_id", citation, first.get("receipt_id"))
            check("receipt_scope", g.scope.model_dump(), first.get("arguments"))
            data = first.get("result", {})
            actual.update(
                total_yuan=data.get("total_yuan"),
                order_count=data.get("order_count"),
                customer_id=data.get("customer_id"),
            )
            for name, value in dict(
                total_cents=g.total_cents,
                rows_returned=g.rows_returned,
                truncated=g.truncated,
                source="day65-fictional-sales",
                query_id="monthly_paid_sales_v1",
                read_only=True,
                currency="CNY",
                order_status="paid",
                data_status="no_data"
                if case.expected.business_status == "no_data"
                else "ok",
            ).items():
                check("receipt_" + name, value, data.get(name))
            check(
                "displayed_order_ids",
                g.displayed_order_ids,
                [r.get("order_id") for r in data.get("orders", [])],
            )
            check(
                "receipt_period",
                {
                    "start": f"{g.scope.year}-{g.scope.month:02d}-01",
                    "end_exclusive": f"{g.scope.year}-{g.scope.month + 1:02d}-01",
                },
                data.get("period"),
            )
            raw_orders = {
                r["order_id"]: r
                for r in read_json(ROOT / "experiments/day65/sales-data.json")["orders"]
            }
            # Check returned monetary details separately from the full-scope total.
            expected_orders = [raw_orders[key] for key in g.displayed_order_ids]
            check("receipt_orders", expected_orders, data.get("orders"))
        check("final_answer", expected_text(case, citation), observed.answer)
        approval = trace.get("approval") or {}
        proposal = approval.get("proposal") or {}
        check("approval_body", observed.answer, proposal.get("body"))
        check("approval_task", observed.task_id, proposal.get("source_task_id"))
        check("approval_run", observed.agent_run_id, proposal.get("agent_run_id"))
        check("approval_fictional", True, proposal.get("fictional"))
        check(
            "answer_source",
            "validated_receipt_fallback"
            if case.behavior.degraded
            else "verified_report_template",
            observed.answer_source,
        )
    else:
        check("no_approval", None, trace.get("approval"))
        check(
            "final_answer",
            "请明确查询的年份和月份，再开始查询。"
            if case.expected.business_status == "needs_clarification"
            else None,
            observed.answer,
        )
        check(
            "answer_source",
            "clarification_template"
            if case.expected.business_status == "needs_clarification"
            else "none",
            observed.answer_source,
        )
    for rule in case.expected.criteria:
        check("criterion_" + rule.criterion_id, rule.expected, actual.get(rule.field))
    failed = [r.rule_id for r in checks if not r.passed]
    return Grade(
        case_id=case.case_id,
        category=case.category,
        judgement="failed" if failed else "passed",
        checks=checks,
        failed_rules=failed,
    )


class ScoredReport(StrictContract):
    schema_version: Literal["day90-scoring-v1"]
    report_kind: Literal["fixed_fixture_rule_evaluation"]
    source: MeteredReport
    source_sha256: Sha256
    scorer_source_sha256_lf: dict[str, Sha256]
    ruleset: Literal["day86-sales-fixture-rules-v1"]
    results: list[Grade]
    summary: dict
    by_category: dict
    full_dataset_evaluated: bool
    grading_executes_agent: Literal[False]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if canonical_hash(self.source.model_dump()) != self.source_sha256:
            raise ValueError("scoring_source_mismatch")
        execution = self.source.execution
        if [r.case_id for r in self.results] != [r.case_id for r in execution.rows]:
            raise ValueError("scoring_coverage_mismatch")
        cases = {c.case_id: c for c in execution.plan.dataset.cases}
        if any(cases[r.case_id].category != r.category for r in self.results):
            raise ValueError("scoring_category_mismatch")
        for grade, row in zip(self.results, execution.rows, strict=True):
            if row.execution_status in {"not_run", "running", "interrupted"}:
                if grade.judgement != "not_evaluated":
                    raise ValueError("unfinished_execution_scored")
            elif row.execution_status in {"error", "timeout"}:
                if grade.judgement != "error" or grade.reason != "execution_error":
                    raise ValueError("execution_error_scored")
            elif (
                grade.judgement not in {"passed", "failed"}
                and grade.reason != "evidence_invalid"
            ):
                raise ValueError("completed_execution_grade_invalid")
        if canonical_hash(self.summary) != canonical_hash(
            summary(self.results)
        ) or canonical_hash(self.by_category) != canonical_hash(
            summary_groups(self.results)
        ):
            raise ValueError("scoring_summary_mismatch")
        full = (
            execution.plan.suite == "full"
            and len(self.results) == len(cases)
            and self.summary["not_evaluated"] == 0
        )
        if self.full_dataset_evaluated != full:
            raise ValueError("full_coverage_claim_mismatch")
        return self
