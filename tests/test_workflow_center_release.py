import json
import re
from pathlib import Path

N8N_DIR = Path(__file__).parents[1] / "n8n"
WORKFLOW_DIR = N8N_DIR / "workflows"
MANIFEST_PATH = N8N_DIR / "workflow-center-v0.1.0.json"
PROJECT_ROOT = Path(__file__).parents[1]

INSTANCE_FIELDS = {
    "id",
    "versionId",
    "activeVersionId",
    "meta",
    "shared",
}

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_release_manifest_identifies_component_versions() -> None:
    manifest = load_json(MANIFEST_PATH)

    assert manifest["product"] == "Workflow Center"
    assert manifest["version"] == "0.1.0"
    assert manifest["release_date"] == "2026-09-04"
    assert manifest["platform"] == {
        "api_version": "1.0.0",
        "n8n_version": "2.36.8",
    }


def test_release_manifest_references_existing_versioned_workflows() -> None:
    manifest = load_json(MANIFEST_PATH)
    declared_files = {item["file"] for item in manifest["workflows"]}
    actual_files = {
        path.relative_to(N8N_DIR).as_posix() for path in WORKFLOW_DIR.glob("*.json")
    }

    assert declared_files <= actual_files
    assert len(declared_files) == 7


def test_manifest_metadata_matches_workflow_exports() -> None:
    manifest = load_json(MANIFEST_PATH)
    names: set[str] = set()

    for item in manifest["workflows"]:
        workflow = load_json(N8N_DIR / item["file"])

        assert workflow["name"] == item["name"]
        assert item["name"] not in names
        assert item["tier"] in {
            "reference",
            "optional",
            "release",
        }
        names.add(item["name"])


def test_release_workflows_are_portable_and_secret_free() -> None:
    manifest = load_json(MANIFEST_PATH)

    for item in manifest["workflows"]:
        workflow = load_json(N8N_DIR / item["file"])
        serialized = json.dumps(workflow)

        assert workflow["active"] is False
        assert workflow["pinData"] == {}
        assert not INSTANCE_FIELDS & workflow.keys()
        assert all("webhookId" not in node for node in workflow["nodes"])
        assert all("credentials" not in node for node in workflow["nodes"])
        assert not any(pattern.search(serialized) for pattern in SECRET_PATTERNS)


def test_release_publish_order_preserves_error_binding() -> None:
    manifest = load_json(MANIFEST_PATH)
    deployment = manifest["deployment"]
    error_workflow = "workflows/w6d41-workflow-error-handler.json"
    main_workflow = "workflows/w6d41-persistent-ai-email-assistant.json"

    assert deployment["publish_order"] == [
        error_workflow,
        main_workflow,
    ]
    assert deployment["import_order"].index(error_workflow) < deployment[
        "import_order"
    ].index(main_workflow)
    assert {
        "workflow": main_workflow,
        "setting": "Error Workflow",
        "target": error_workflow,
    } in deployment["manual_bindings"]


def test_release_declares_runtime_and_quality_requirements() -> None:
    manifest = load_json(MANIFEST_PATH)

    assert set(manifest["required_environment_variables"]) == {
        "N8N_ENCRYPTION_KEY",
        "DIFY_WORKFLOW_API_KEY",
    }
    assert {
        "pytest",
        "ruff",
        "docker_health",
        "openapi",
        "n8n_portability",
        "n8n_security_audit",
        "success_human_duplicate_failure_replay",
    } <= set(manifest["quality_gates"])


def test_release_documentation_is_complete_and_indexed() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    docs_index = (PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    weekly_doc = PROJECT_ROOT / "docs" / "week-6.md"
    assert weekly_doc.is_file()
    content = weekly_doc.read_text(encoding="utf-8")
    for anchor in ("workflow-center-v0.1", "summary"):
        assert f'<a id="{anchor}"></a>' in content
        assert f"docs/week-6.md#{anchor}" in readme
    assert "week-6.md" in docs_index
    assert "[Workflow Center 0.1.0] - 2026-09-04" in changelog
