"""Deterministic acceptance oracle for the Day 61 scenario, not an Agent runtime."""

from datetime import datetime, timedelta, timezone

from sales_contract import Gap, Recommendation, SalesReport, ScenarioInput

LOCAL_TIME = timezone(timedelta(hours=8))
CATEGORY_ORDER = {
    "manual_review": 0,
    "needs_information": 1,
    "priority_followup": 2,
    "routine_followup": 3,
}


def assess(source: ScenarioInput) -> SalesReport:
    request = source.request
    scope = request.model_copy(
        update={
            "customer_ids": sorted(request.customer_ids)
            if request.customer_ids
            else None
        }
    )
    missing = request.missing_fields()
    if missing:
        return SalesReport(
            scope=scope,
            status="waiting_for_input",
            missing_fields=missing,
            recommendations=[],
            gaps=[],
        )
    recommendations = []
    gaps = []
    for snapshot in sorted(source.snapshots, key=lambda item: item.customer_id):
        customer_id = snapshot.customer_id
        if snapshot.fetch_status != "ok":
            gaps.append(
                Gap(
                    customer_id=customer_id,
                    reason="source_error"
                    if snapshot.fetch_status == "error"
                    else "not_found",
                    evidence_ids=[],
                )
            )
            continue
        records = sorted(
            (
                record
                for record in snapshot.records
                if request.period_start
                <= datetime.fromisoformat(record.created_at)
                .astimezone(LOCAL_TIME)
                .date()
                .isoformat()
                <= request.period_end
            ),
            key=lambda record: (
                datetime.fromisoformat(record.created_at),
                record.followup_id,
            ),
        )
        if not records:
            gaps.append(
                Gap(customer_id=customer_id, reason="no_records", evidence_ids=[])
            )
            continue
        latest_time = datetime.fromisoformat(records[-1].created_at)
        latest = [
            r for r in records if datetime.fromisoformat(r.created_at) == latest_time
        ]
        if len({r.priority for r in latest}) != 1:
            gaps.append(
                Gap(
                    customer_id=customer_id,
                    reason="conflicting_priority",
                    evidence_ids=sorted(r.followup_id for r in latest),
                )
            )
            continue
        # A later record is not evidence that an earlier risk was resolved.
        risks = sorted({flag for r in records for flag in r.risk_flags})
        missing_info = sorted({item for r in records for item in r.missing_information})
        evidence = sorted(r.followup_id for r in records)
        if risks:
            category, reason, action = "manual_review", "review_pending", "review_risks"
            gaps.append(
                Gap(
                    customer_id=customer_id,
                    reason="review_required",
                    evidence_ids=evidence,
                )
            )
        elif missing_info:
            category, reason, action = (
                "needs_information",
                "missing_information",
                "collect_missing_information",
            )
        elif latest[0].priority == "high":
            category, reason, action = (
                "priority_followup",
                "latest_priority_high",
                "prepare_followup",
            )
        else:
            category, reason, action = (
                "routine_followup",
                "latest_priority_normal",
                "maintain_followup",
            )
        if missing_info:
            gaps.append(
                Gap(
                    customer_id=customer_id,
                    reason="missing_information",
                    evidence_ids=evidence,
                )
            )
        recommendations.append(
            Recommendation(
                customer_id=customer_id,
                category=category,
                reason_code=reason,
                suggested_action=action,
                evidence_ids=evidence,
                missing_information=missing_info,
                risk_flags=risks,
            )
        )
    recommendations.sort(
        key=lambda item: (CATEGORY_ORDER[item.category], item.customer_id)
    )
    if all(item.fetch_status == "error" for item in source.snapshots):
        status = "failed"
    elif len(gaps) == len(source.snapshots) and all(
        g.reason == "no_records" for g in gaps
    ):
        status = "no_data"
    elif gaps:
        status = "incomplete"
    else:
        status = "completed"
    return SalesReport(
        scope=scope,
        status=status,
        missing_fields=[],
        recommendations=recommendations,
        gaps=gaps,
    )


def validate_report(source: ScenarioInput, report: SalesReport) -> None:
    """Check coverage, priorities and exact source IDs, beyond JSON shape validation."""
    if report != assess(source):
        raise ValueError("report_does_not_match_evidence_rules")
