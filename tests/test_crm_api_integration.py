from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import database
from backend.app.routers.crm import router as crm_router
from backend.app.routers.workflow import router as workflow_router


def test_crm_api_persists_and_queries_followup_without_duplicate_side_effects(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "crm-api-integration.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    database.init_database()

    app = FastAPI()
    app.include_router(workflow_router)
    app.include_router(crm_router)

    with TestClient(app) as client:
        start_response = client.post(
            "/workflow-runs/start",
            json={
                "event_id": "sales-integration-001",
                "workflow_name": "sales-followup-assistant",
                "source": "manual_demo",
                "requester": "sales-demo",
                "report_date": "2026-09-09",
                "input_data": {
                    "customer_id": "customer-integration-001",
                    "company_name": "示例集成测试企业",
                },
                "n8n_execution_id": "execution-integration-001",
            },
        )

        assert start_response.status_code == 200
        assert start_response.json()["should_process"] is True
        run_id = start_response.json()["run_id"]

        followup_payload = {
            "customer": {
                "customer_id": "customer-integration-001",
                "company_name": "示例集成测试企业",
                "industry": "制造业",
                "sales_owner": "sales-demo",
            },
            "run_id": run_id,
            "event_id": "sales-integration-001",
            "requirement_snapshot": "希望建设内部知识库",
            "analysis": {
                "summary": "客户希望建设内部知识库。",
                "needs": ["建设内部知识库"],
                "missing_information": ["文档规模", "部署环境"],
                "next_actions": ["确认文档规模", "了解部署环境"],
                "risk_flags": [],
            },
            "priority": "high",
            "review_status": "not_required",
            "review_reasons": [],
            "notification_mode": "preview",
            "notification_channel": "feishu",
        }

        create_response = client.post(
            "/crm/followups",
            json=followup_payload,
        )
        assert create_response.status_code == 200
        assert create_response.json()["created"] is True
        assert create_response.json()["notification_status"] == "preview"
        followup_id = create_response.json()["followup_id"]

        duplicate_payload = {
            **followup_payload,
            "customer": {
                **followup_payload["customer"],
                "company_name": "重复请求不应覆盖客户",
            },
        }
        duplicate_response = client.post(
            "/crm/followups",
            json=duplicate_payload,
        )
        assert duplicate_response.status_code == 200
        assert duplicate_response.json()["created"] is False
        assert duplicate_response.json()["followup_id"] == followup_id

        customer_response = client.get(
            "/crm/customers/customer-integration-001"
        )
        assert customer_response.status_code == 200
        assert customer_response.json()["company_name"] == "示例集成测试企业"

        followup_response = client.get(f"/crm/followups/{followup_id}")
        assert followup_response.status_code == 200
        assert followup_response.json()["run_id"] == run_id
        assert followup_response.json()["analysis"]["needs"] == [
            "建设内部知识库"
        ]

        list_response = client.get(
            "/crm/customers/customer-integration-001/followups"
        )
        assert list_response.status_code == 200
        assert list_response.json()["count"] == 1
        assert list_response.json()["followups"][0]["followup_id"] == followup_id

        update_response = client.put(
            "/crm/customers/customer-integration-001",
            json={
                "customer_id": "customer-integration-001",
                "company_name": "示例集成测试企业更新",
                "industry": None,
                "sales_owner": "sales-owner-002",
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["company_name"] == "示例集成测试企业更新"
        assert update_response.json()["industry"] is None
        assert update_response.json()["sales_owner"] == "sales-owner-002"

    connection = database.get_connection()
    try:
        customer_count = connection.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]
        followup_count = connection.execute(
            "SELECT COUNT(*) FROM followup_records"
        ).fetchone()[0]
        workflow_status = connection.execute(
            "SELECT status FROM workflow_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert customer_count == 1
    assert followup_count == 1
    assert workflow_status == "running"
