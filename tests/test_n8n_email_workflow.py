import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parents[1]
    / "n8n"
    / "workflows"
    / "w6d39-ai-email-assistant.json"
)


def load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def assignment_names(node: dict) -> set[str]:
    assignments = node["parameters"]["assignments"]["assignments"]
    return {assignment["name"] for assignment in assignments}


def test_email_workflow_is_portable_and_inactive() -> None:
    workflow = load_workflow()

    assert workflow["active"] is False
    assert workflow["pinData"] == {}
    assert not {"id", "versionId", "meta"} & workflow.keys()
    assert all("webhookId" not in node for node in workflow["nodes"])
    assert all("credentials" not in node for node in workflow["nodes"])


def test_email_workflow_has_expected_nodes_and_webhook_contract() -> None:
    workflow = load_workflow()
    webhook = node_by_name(workflow, "Receive Customer Request")
    response = node_by_name(workflow, "Return JSON Response")

    assert workflow["name"] == "W6D39 - AI Email Assistant"
    assert len(workflow["nodes"]) == 8
    assert len(workflow["connections"]) == 7
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == "w6d39-ai-email-assistant"
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert response["parameters"]["options"]["responseCode"] == 200


def test_email_workflow_routes_review_and_draft_branches() -> None:
    workflow = load_workflow()
    branches = workflow["connections"]["Needs Human Review?"]["main"]

    assert branches[0][0]["node"] == "Build Human Review Response"
    assert branches[1][0]["node"] == "Call AI Workflow"

    for source, connection in workflow["connections"].items():
        assert node_by_name(workflow, source)
        for output in connection["main"]:
            for target in output:
                assert node_by_name(workflow, target["node"])


def test_email_workflow_classifier_enforces_review_rules() -> None:
    workflow = load_workflow()
    classifier = node_by_name(workflow, "Classify Email Request")["parameters"][
        "jsCode"
    ]

    assert "missing_required_fields" in classifier
    assert "high_priority" in classifier
    assert "sensitive_content:" in classifier
    assert "ambiguous_request" in classifier
    assert "human_review" in classifier
    assert "ai_draft_generation" in classifier


def test_email_workflow_uses_stable_response_contract() -> None:
    workflow = load_workflow()
    human_fields = assignment_names(
        node_by_name(workflow, "Build Human Review Response")
    )
    draft_fields = assignment_names(
        node_by_name(workflow, "Build Email Draft Response")
    )

    expected_fields = {
        "accepted",
        "day",
        "event_id",
        "source",
        "requester",
        "category",
        "priority",
        "summary",
        "draft_reply",
        "need_human_review",
        "review_reason",
        "status",
        "task_id",
        "workflow_run_id",
        "elapsed_time",
        "total_tokens",
        "total_steps",
        "next_step",
        "execution_mode",
        "received_at",
        "processed_at",
    }

    assert human_fields == expected_fields
    assert draft_fields == expected_fields


def test_email_workflow_calls_internal_ai_boundary() -> None:
    workflow = load_workflow()
    ai_node = node_by_name(workflow, "Call AI Workflow")
    body_fields = {
        parameter["name"]
        for parameter in ai_node["parameters"]["bodyParameters"]["parameters"]
    }

    assert ai_node["parameters"]["method"] == "POST"
    assert ai_node["parameters"]["url"] == "http://api:8000/dify/workflow"
    assert ai_node["parameters"]["options"]["timeout"] == 120000
    assert body_fields == {"question", "user"}
