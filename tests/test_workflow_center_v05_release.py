import json
import re
from datetime import date
from pathlib import Path

N8N_DIR = Path(__file__).parents[1] / "n8n"
MANIFEST_PATH = N8N_DIR / "workflow-center-v0.5.0.json"
SALES = "workflows/w7d47-sales-followup-assistant.json"
EMAIL = "workflows/w6d41-persistent-ai-email-assistant.json"
ERROR = "workflows/w6d41-workflow-error-handler.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v05_identifies_component_and_release_state() -> None:
    manifest = load_json(MANIFEST_PATH)
    assert manifest["product"] == "Workflow Center"
    assert manifest["version"] == "0.5.0"
    assert manifest["git_tag"] == "workflow-center-v0.5.0"
    assert manifest["platform"] == {
        "api_version": "1.0.0",
        "n8n_version": "2.36.8",
    }
    assert manifest["release_status"] in {"draft", "candidate", "released"}
    if manifest["release_status"] == "released":
        date.fromisoformat(manifest["release_date"])
    else:
        assert manifest["release_date"] is None


def test_v05_inventory_covers_exports_without_duplicates() -> None:
    manifest = load_json(MANIFEST_PATH)
    files = [item["file"] for item in manifest["workflows"]]
    actual = {
        path.relative_to(N8N_DIR).as_posix()
        for path in (N8N_DIR / "workflows").glob("*.json")
    }
    previous = load_json(N8N_DIR / "workflow-center-v0.1.0.json")
    historical = {item["file"] for item in previous["workflows"]}
    assert len(files) == len(set(files))
    assert set(files) == actual == historical | {SALES}
    names = []
    for item in manifest["workflows"]:
        workflow = load_json(N8N_DIR / item["file"])
        assert item["name"] == workflow["name"]
        assert item["tier"] in {"reference", "optional", "release"}
        assert item["publish_by_default"] is (item["tier"] == "release")
        types = {node["type"] for node in workflow["nodes"]}
        if "n8n-nodes-base.scheduleTrigger" in types:
            expected_trigger = "schedule_and_webhook"
            assert "n8n-nodes-base.webhook" in types
        elif "n8n-nodes-base.errorTrigger" in types:
            expected_trigger = "error"
        elif "n8n-nodes-base.webhook" in types:
            expected_trigger = "webhook"
        else:
            assert "n8n-nodes-base.manualTrigger" in types
            expected_trigger = "manual"
        assert item["trigger"] == expected_trigger
        names.append(item["name"])
    assert len(names) == len(set(names))


def test_v05_orders_cover_inventory_and_respect_dependencies() -> None:
    manifest = load_json(MANIFEST_PATH)
    items = {item["file"]: item for item in manifest["workflows"]}
    deployment = manifest["deployment"]
    imports = deployment["import_order"]
    publish = deployment["publish_order"]
    assert len(imports) == len(set(imports))
    assert set(imports) == set(items)
    assert len(publish) == len(set(publish))
    assert set(publish) == {
        path for path, item in items.items() if item["publish_by_default"]
    }
    for path, item in items.items():
        for dependency in item["workflow_dependencies"]:
            assert dependency in items
            assert imports.index(dependency) < imports.index(path)
            if path in publish:
                assert dependency in publish
                assert publish.index(dependency) < publish.index(path)
    assert items[EMAIL]["workflow_dependencies"] == [ERROR]
    assert items[SALES]["workflow_dependencies"] == []


def test_v05_runtime_dependencies_match_workflow_nodes() -> None:
    manifest = load_json(MANIFEST_PATH)
    definitions = manifest["runtime_dependencies"]
    for item in manifest["workflows"]:
        workflow = load_json(N8N_DIR / item["file"])
        urls = [node["parameters"].get("url", "") for node in workflow["nodes"]]
        expected = {"n8n"}
        if any("http://api:8000/" in url for url in urls):
            expected.add("api")
        if any("/dify/workflow" in url for url in urls):
            expected.add("dify")
        if any(node["type"].endswith(".lmChatOpenAi") for node in workflow["nodes"]):
            expected.add("qwen_credential")
        if any("/workflow-runs/" in url or "/crm/" in url for url in urls):
            expected.add("sqlite")
        dependencies = item["runtime_dependencies"]
        assert len(dependencies) == len(set(dependencies))
        assert set(dependencies) == expected
        assert expected <= definitions.keys()
    assert definitions["api"]["version"] == manifest["platform"]["api_version"]
    assert definitions["n8n"]["version"] == manifest["platform"]["n8n_version"]
    required_env = {
        variable
        for definition in definitions.values()
        for variable in definition.get("required_environment_variables", [])
    }
    assert set(manifest["required_environment_variables"]) == required_env


def test_v05_manual_bindings_resolve_to_real_nodes_and_workflows() -> None:
    manifest = load_json(MANIFEST_PATH)
    workflows = {
        item["file"]: load_json(N8N_DIR / item["file"])
        for item in manifest["workflows"]
    }
    expected_models = {
        (path, node["name"])
        for path, workflow in workflows.items()
        for node in workflow["nodes"]
        if node["type"].endswith(".lmChatOpenAi")
    }
    models = []
    error_bindings = []
    for binding in manifest["deployment"]["manual_bindings"]:
        assert binding["workflow"] in workflows
        if binding["kind"] == "credential":
            key = (binding["workflow"], binding["node"])
            assert key in expected_models
            models.append(key)
            definition = manifest["runtime_dependencies"][binding["target"]]
            assert binding["credential_type"] == definition["credential_type"]
            node = next(
                node
                for node in workflows[binding["workflow"]]["nodes"]
                if node["name"] == binding["node"]
            )
            assert node["parameters"]["model"]["value"] == definition["model"]
        else:
            assert binding["kind"] == "error_workflow"
            assert binding["setting"] == "Error Workflow"
            assert any(
                node["type"] == "n8n-nodes-base.errorTrigger"
                for node in workflows[binding["target"]]["nodes"]
            )
            error_bindings.append((binding["workflow"], binding["target"]))
    assert len(models) == len(set(models))
    assert set(models) == expected_models
    assert error_bindings == [(EMAIL, ERROR)]


def test_v05_exports_are_portable_and_no_secrets_are_embedded() -> None:
    manifest = load_json(MANIFEST_PATH)
    for item in manifest["workflows"]:
        workflow = load_json(N8N_DIR / item["file"])
        assert workflow["active"] is False
        assert workflow["pinData"] == {}
        assert (
            not {
                "id",
                "versionId",
                "activeVersionId",
                "meta",
                "shared",
                "projectId",
            }
            & workflow.keys()
        )
        assert "errorWorkflow" not in workflow["settings"]
        for node in workflow["nodes"]:
            assert not {"credentials", "webhookId"} & node.keys()
        serialized = json.dumps(workflow)
        assert not re.search(r"sk-[A-Za-z0-9_-]{16,}", serialized)
        assert not re.search(r"Bearer\s+[A-Za-z0-9._-]{16,}", serialized, re.IGNORECASE)


def test_v05_sales_scope_preserves_preview_and_existing_webhook() -> None:
    manifest = load_json(MANIFEST_PATH)
    scope = manifest["scope"]
    workflow = load_json(N8N_DIR / SALES)
    nodes = {node["name"]: node for node in workflow["nodes"]}
    build = nodes["Build CRM Follow-up Payload"]["parameters"]["jsCode"]
    assert scope["sales_notification_mode"] == "preview"
    assert scope["sales_notification_channel"] == "feishu"
    assert "notification_mode: 'preview'" in build
    assert "notification_channel: 'feishu'" in build
    assert scope["sales_live_notification_orchestration"] is False
    assert scope["notification_failure_validation"] == "simulated_state_api"
    assert not any(
        "/integrations/" in node["parameters"].get("url", "")
        for node in workflow["nodes"]
    )
    webhook = nodes["Receive Sales Lead"]["parameters"]
    assert webhook["path"] == "w7d47-sales-followup-assistant"
    assert webhook["httpMethod"] == "POST"
    assert {
        "day48_workflow_node_regression",
        "sales_production_success_and_duplicate",
        "sales_ai_invalid_output_and_service_failure",
        "crm_checkpoint_recovery",
        "notification_state_and_resolution_simulation",
        "crm_saved_replay_guard",
    } <= set(manifest["quality_gates"])
