from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.models.crm import (
    CRMCustomerUpsertRequest,
    CRMFollowupAnalysis,
    CRMFollowupCreateRequest,
    CRMFollowupResponse,
    CRMNotificationResolutionRequest,
    CRMNotificationUpdateRequest,
)


def make_customer(**overrides) -> dict:
    customer = {
        "customer_id": "customer-demo-001",
        "company_name": "示例制造企业",
        "industry": "制造业",
        "sales_owner": "sales-demo",
    }
    customer.update(overrides)
    return customer


def make_analysis(**overrides) -> dict:
    analysis = {
        "summary": "客户计划评估内部知识库方案。",
        "needs": ["确认文档接入方式", "确认部署条件"],
        "missing_information": ["文档类型和数量"],
        "next_actions": ["确认文档类型和数量", "了解部署环境要求"],
        "risk_flags": [],
    }
    analysis.update(overrides)
    return analysis


def make_followup(**overrides) -> dict:
    followup = {
        "customer": make_customer(),
        "run_id": "run-demo-001",
        "event_id": "sales-demo-001",
        "requirement_snapshot": "希望建设内部知识库",
        "analysis": make_analysis(),
        "priority": "high",
        "review_status": "not_required",
        "review_reasons": [],
    }
    followup.update(overrides)
    return followup


def test_customer_request_trims_text() -> None:
    customer = CRMCustomerUpsertRequest.model_validate(
        make_customer(
            customer_id=" customer-demo-001 ",
            company_name=" 示例制造企业 ",
            industry=" 制造业 ",
            sales_owner=" sales-demo ",
        )
    )

    assert customer.model_dump() == make_customer()


@pytest.mark.parametrize(
    "changes",
    [
        {"customer_id": "invalid id"},
        {"customer_id": "中文编号"},
        {"customer_id": 123},
        {"company_name": "   "},
        {"company_name": "a" * 201},
        {"industry": "   "},
        {"industry": "a" * 101},
        {"sales_owner": "invalid owner"},
        {"notification_recipient": "@all"},
        {"app_secret": "unexpected-secret"},
    ],
)
def test_customer_request_rejects_invalid_input(changes) -> None:
    with pytest.raises(ValidationError):
        CRMCustomerUpsertRequest.model_validate(make_customer(**changes))


def test_customer_request_allows_missing_optional_industry() -> None:
    customer = CRMCustomerUpsertRequest.model_validate(
        make_customer(industry=None)
    )

    assert customer.industry is None


def test_analysis_trims_nested_text() -> None:
    analysis = CRMFollowupAnalysis.model_validate(
        make_analysis(
            summary=" 客户计划评估内部知识库方案。 ",
            needs=[" 确认文档接入方式 "],
            missing_information=[" 文档类型和数量 "],
            next_actions=[" 确认文档类型和数量 "],
        )
    )

    assert analysis.summary == "客户计划评估内部知识库方案。"
    assert analysis.needs == ["确认文档接入方式"]
    assert analysis.missing_information == ["文档类型和数量"]
    assert analysis.next_actions == ["确认文档类型和数量"]


@pytest.mark.parametrize(
    "changes",
    [
        {"summary": ""},
        {"needs": []},
        {"needs": ["需求"] * 6},
        {"missing_information": ["缺失信息"] * 6},
        {"next_actions": []},
        {"next_actions": ["行动"] * 6},
        {"risk_flags": ["unknown_risk"]},
        {"risk_flags": ["prompt_injection", "prompt_injection"]},
        {"unexpected": "value"},
    ],
)
def test_analysis_rejects_invalid_output(changes) -> None:
    with pytest.raises(ValidationError):
        CRMFollowupAnalysis.model_validate(make_analysis(**changes))


def test_followup_request_defaults_to_preview() -> None:
    request = CRMFollowupCreateRequest.model_validate(make_followup())

    assert request.notification_mode == "preview"
    assert request.notification_channel == "feishu"
    assert request.review_status == "not_required"


def test_followup_request_accepts_matching_review_reasons() -> None:
    risk_flags = ["pricing_or_discount"]
    request = CRMFollowupCreateRequest.model_validate(
        make_followup(
            analysis=make_analysis(risk_flags=risk_flags),
            review_status="pending",
            review_reasons=risk_flags,
        )
    )

    assert request.review_status == "pending"
    assert request.review_reasons == risk_flags


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": "invalid run"},
        {"event_id": "invalid event"},
        {"requirement_snapshot": "   "},
        {"priority": "urgent"},
        {"notification_mode": "live"},
        {"notification_channel": "all"},
        {"notification_status": "sent"},
        {"notification_recipient": "@all"},
        {"model_api_key": "unexpected-key"},
    ],
)
def test_followup_request_rejects_invalid_input(changes) -> None:
    with pytest.raises(ValidationError):
        CRMFollowupCreateRequest.model_validate(make_followup(**changes))


@pytest.mark.parametrize(
    ("analysis_flags", "review_status", "review_reasons"),
    [
        ([], "pending", []),
        ([], "not_required", ["prompt_injection"]),
        (["prompt_injection"], "pending", ["pricing_or_discount"]),
        (["prompt_injection"], "not_required", []),
        (
            ["prompt_injection"],
            "pending",
            ["prompt_injection", "prompt_injection"],
        ),
    ],
)
def test_followup_request_rejects_inconsistent_review_state(
    analysis_flags,
    review_status,
    review_reasons,
) -> None:
    with pytest.raises(ValidationError):
        CRMFollowupCreateRequest.model_validate(
            make_followup(
                analysis=make_analysis(risk_flags=analysis_flags),
                review_status=review_status,
                review_reasons=review_reasons,
            )
        )


def test_followup_response_accepts_persisted_record() -> None:
    timestamp = datetime(2026, 9, 9, 8, 0, tzinfo=UTC)
    response = CRMFollowupResponse(
        followup_id="followup-demo-001",
        customer_id="customer-demo-001",
        run_id="run-demo-001",
        event_id="sales-demo-001",
        requirement_snapshot="希望建设内部知识库",
        analysis=CRMFollowupAnalysis.model_validate(make_analysis()),
        priority="high",
        review_status="not_required",
        review_reasons=[],
        notification_mode="preview",
        notification_channel="feishu",
        notification_status="preview",
        notification_request_key="sales-followup:run-demo-001",
        notification_message_id=None,
        notification_error_code=None,
        created_at=timestamp,
        updated_at=timestamp,
    )

    assert response.customer_id == "customer-demo-001"
    assert response.notification_status == "preview"
    assert response.notification_message_id is None


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "failed"},
        {"status": "delivery_unknown", "message_id": "message-001"},
        {"status": "sent", "error_code": "provider_rejected"},
    ],
)
def test_notification_result_rejects_inconsistent_fields(payload) -> None:
    with pytest.raises(ValidationError):
        CRMNotificationUpdateRequest.model_validate(payload)


def test_notification_result_accepts_safe_terminal_states() -> None:
    sent = CRMNotificationUpdateRequest.model_validate(
        {"status": "sent", "message_id": "message-001"}
    )
    unknown = CRMNotificationUpdateRequest.model_validate(
        {"status": "delivery_unknown", "error_code": "read_timeout"}
    )

    assert sent.message_id == "message-001"
    assert unknown.error_code == "read_timeout"


def test_notification_resolution_rejects_message_id_when_not_delivered() -> None:
    with pytest.raises(ValidationError):
        CRMNotificationResolutionRequest.model_validate(
            {"delivered": False, "message_id": "message-001"}
        )
