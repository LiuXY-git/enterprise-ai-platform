import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parents[1]
    / "n8n"
    / "workflows"
    / "w7d47-sales-followup-assistant.json"
)


def load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def test_sales_followup_workflow_is_portable_and_inactive() -> None:
    workflow = load_workflow()
    serialized = json.dumps(workflow)

    assert workflow["active"] is False
    assert workflow["pinData"] == {}
    assert not {
        "id",
        "versionId",
        "activeVersionId",
        "meta",
        "shared",
    } & workflow.keys()
    assert all("webhookId" not in node for node in workflow["nodes"])
    assert all("credentials" not in node for node in workflow["nodes"])
    assert "projectId" not in serialized


def test_sales_followup_workflow_has_expected_nodes_and_webhook() -> None:
    workflow = load_workflow()
    webhook = node_by_name(workflow, "Receive Sales Lead")

    assert workflow["name"] == "W7D47 - Sales Follow-up Assistant"
    assert len(workflow["nodes"]) == 15
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == (
        "w7d47-sales-followup-assistant"
    )
    assert webhook["parameters"]["responseMode"] == "responseNode"


def test_sales_followup_workflow_routes_validation_and_duplicates() -> None:
    workflow = load_workflow()
    input_branches = workflow["connections"]["Input Valid?"]["main"]
    process_branches = workflow["connections"]["Should Process?"]["main"]

    assert input_branches[0][0]["node"] == "Start Workflow Run"
    assert input_branches[1][0]["node"] == "Reject Invalid Input"
    assert process_branches[0][0]["node"] == "Analyze Sales Lead"
    assert process_branches[1][0]["node"] == "Return Duplicate Result"

    invalid_response = node_by_name(
        workflow, "Reject Invalid Input"
    )["parameters"]
    duplicate_response = node_by_name(
        workflow, "Return Duplicate Result"
    )["parameters"]
    assert invalid_response["options"]["responseCode"] == 422
    assert "JSON.stringify" in invalid_response["responseBody"]
    assert duplicate_response["options"]["responseCode"] == 200
    assert "JSON.stringify" in duplicate_response["responseBody"]


def test_sales_followup_workflow_uses_structured_ai_output() -> None:
    workflow = load_workflow()
    analysis = node_by_name(workflow, "Analyze Sales Lead")
    parser = node_by_name(workflow, "Validate Sales Analysis")
    model = node_by_name(workflow, "DashScope Qwen Chat Model")
    schema = json.loads(parser["parameters"]["inputSchema"])

    assert analysis["parameters"]["hasOutputParser"] is True
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "summary",
        "needs",
        "missing_information",
        "next_actions",
        "risk_flags",
    }
    assert set(schema["properties"]["risk_flags"]["items"]["enum"]) == {
        "product_capability_unverified",
        "pricing_or_discount",
        "delivery_commitment",
        "prompt_injection",
        "sensitive_information",
    }
    assert model["parameters"]["model"]["value"] == "qwen3.7-plus"
    assert model["parameters"]["responsesApiEnabled"] is False


def test_sales_followup_workflow_persists_crm_and_run_result() -> None:
    workflow = load_workflow()
    start = node_by_name(workflow, "Start Workflow Run")["parameters"]
    build = node_by_name(
        workflow, "Build CRM Follow-up Payload"
    )["parameters"]["jsCode"]
    save = node_by_name(workflow, "Save CRM Follow-up")["parameters"]
    finish = node_by_name(workflow, "Finish Workflow Run")["parameters"]

    assert start["method"] == "POST"
    assert start["url"] == "http://api:8000/workflow-runs/start"
    assert "JSON.stringify" in start["jsonBody"]
    assert '"workflow_name": "sales-followup-assistant"' in (
        start["jsonBody"]
    )
    assert "purchase_window_days <= 30" in build
    assert "notification_mode: 'preview'" in build
    assert "notification_channel: 'feishu'" in build
    assert save["method"] == "POST"
    assert save["url"] == "http://api:8000/crm/followups"
    assert "JSON.stringify($json)" in save["jsonBody"]
    assert finish["method"] == "PATCH"
    assert "/workflow-runs/" in finish["url"]
    assert '"needs_human_review"' in finish["jsonBody"]
    assert '"succeeded"' in finish["jsonBody"]


def test_sales_followup_workflow_returns_stable_success_contract() -> None:
    workflow = load_workflow()
    response = node_by_name(workflow, "Return Success Result")["parameters"]
    body = response["responseBody"]

    assert response["options"]["responseCode"] == 200
    assert "JSON.stringify" in body
    for field in (
        "run_id",
        "followup_id",
        "customer_id",
        "status",
        "duplicate",
        "priority",
        "requires_human_review",
        "review_reasons",
        "analysis",
        "notification",
    ):
        assert f'"{field}"' in body
