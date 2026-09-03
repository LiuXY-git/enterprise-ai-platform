import json
from pathlib import Path

WORKFLOW_DIR = Path(__file__).parents[1] / "n8n" / "workflows"
MAIN_WORKFLOW_PATH = (
    WORKFLOW_DIR / "w6d41-persistent-ai-email-assistant.json"
)
ERROR_WORKFLOW_PATH = WORKFLOW_DIR / "w6d41-workflow-error-handler.json"


def load_workflow(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def assert_portable(workflow: dict) -> None:
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
    assert "workflow-day41-failure-test" not in serialized


def test_day41_workflows_are_portable_and_inactive() -> None:
    assert_portable(load_workflow(MAIN_WORKFLOW_PATH))
    assert_portable(load_workflow(ERROR_WORKFLOW_PATH))


def test_main_workflow_has_persistence_nodes_and_webhook() -> None:
    workflow = load_workflow(MAIN_WORKFLOW_PATH)
    webhook = node_by_name(workflow, "Receive Customer Request")

    assert workflow["name"] == "W6D41 - Persistent AI Email Assistant"
    assert len(workflow["nodes"]) == 14
    assert webhook["parameters"]["httpMethod"] == "POST"
    assert webhook["parameters"]["path"] == (
        "w6d41-persistent-ai-email-assistant"
    )
    assert webhook["parameters"]["responseMode"] == "responseNode"
    assert "errorWorkflow" not in workflow["settings"]


def test_main_workflow_registers_runs_and_supports_replay() -> None:
    workflow = load_workflow(MAIN_WORKFLOW_PATH)
    normalize = node_by_name(workflow, "Normalize Email Request")
    start = node_by_name(workflow, "Start Workflow Run")
    assignments = normalize["parameters"]["assignments"]["assignments"]
    replay = next(item for item in assignments if item["name"] == "replay")
    body = start["parameters"]["jsonBody"]

    assert replay["type"] == "boolean"
    assert "$json.body.replay === true" in replay["value"]
    assert start["parameters"]["method"] == "POST"
    assert start["parameters"]["url"] == (
        "http://api:8000/workflow-runs/start"
    )
    assert '"n8n_execution_id": String($execution.id)' in body
    assert '"replay": $json.replay === true' in body
    assert start["parameters"]["options"]["timeout"] == 10000


def test_main_workflow_skips_duplicates_and_persists_results() -> None:
    workflow = load_workflow(MAIN_WORKFLOW_PATH)
    should_process = workflow["connections"]["Should Process?"]["main"]
    finish = node_by_name(workflow, "Finish Workflow Run")
    finish_body = finish["parameters"]["jsonBody"]

    assert should_process[0][0]["node"] == "Restore Workflow Context"
    assert should_process[1][0]["node"] == "Build Duplicate Response"
    assert workflow["connections"]["Build Duplicate Response"]["main"][0][0][
        "node"
    ] == "Return JSON Response"
    assert finish["parameters"]["method"] == "PATCH"
    assert "/workflow-runs/" in finish["parameters"]["url"]
    assert '"output_data": $json' in finish_body
    assert '"needs_human_review"' in finish_body
    assert workflow["connections"]["Finish Workflow Run"]["main"][0][0][
        "node"
    ] == "Restore Final Response"


def test_error_workflow_persists_automatic_failures() -> None:
    workflow = load_workflow(ERROR_WORKFLOW_PATH)
    trigger = node_by_name(workflow, "Error Trigger")
    request = node_by_name(workflow, "Persist Workflow Failure")
    body = request["parameters"]["jsonBody"]

    assert workflow["name"] == "W6D41 - Workflow Error Handler"
    assert len(workflow["nodes"]) == 2
    assert trigger["type"] == "n8n-nodes-base.errorTrigger"
    assert request["parameters"]["method"] == "PATCH"
    assert "$json.execution.id" in request["parameters"]["url"]
    assert request["parameters"]["url"].endswith('/failure"\n}}')
    assert body.startswith("={{")
    assert not body.startswith("=={{")
    assert '"error_type": "n8n_execution_error"' in body
    assert request["onError"] == "continueRegularOutput"
