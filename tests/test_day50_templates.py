import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "n8n/templates/catalog.json").read_text(encoding="utf-8"))
SCRIPT = ROOT / "scripts/day50/render_template_request.py"
SPEC = importlib.util.spec_from_file_location("day50_renderer", SCRIPT)
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)
CASES = [
    (template, example)
    for template in CATALOG["templates"]
    for example in template["examples"]
]


@pytest.mark.parametrize("template", CATALOG["templates"], ids=lambda t: t["id"])
def test_catalog_resolves_real_webhooks_and_bindings(template):
    workflow = json.loads((ROOT / template["workflow"]).read_text(encoding="utf-8"))
    assert (ROOT / template["guide"]).is_file()
    webhooks = [n for n in workflow["nodes"] if n["type"].endswith(".webhook")]
    assert len(webhooks) == 1
    assert webhooks[0]["parameters"]["path"] == template["webhook_path"]
    assert webhooks[0]["parameters"]["httpMethod"] == "POST"
    assert template["import_order"][-1] == template["workflow"]
    for dependency in template["import_order"]:
        assert (ROOT / dependency).is_file()
    for binding in template["bindings"]:
        if binding["kind"] == "error_workflow":
            dependency = json.loads(
                (ROOT / binding["target"]).read_text(encoding="utf-8")
            )
            assert binding["target"] in template["import_order"][:-1]
            assert any(n["type"].endswith(".errorTrigger") for n in dependency["nodes"])
        else:
            node = next(n for n in workflow["nodes"] if n["name"] == binding["node"])
            assert node["type"].endswith(".lmChatOpenAi")
    requests = [n for n in workflow["nodes"] if n["type"].endswith(".httpRequest")]
    persistent = any(
        "/workflow-runs/start" in n["parameters"].get("url", "") for n in requests
    )
    assert template["platform_persistence"] is persistent
    if persistent:
        start = next(n for n in requests if n["name"] == "Start Workflow Run")
        assert template["platform_workflow_name"] in start["parameters"]["jsonBody"]
    else:
        assert template["platform_workflow_name"] is None
        assert template["duplicate_protection"] is False


@pytest.mark.parametrize("template,example", CASES)
def test_examples_render_fresh_requests_without_modifying_sources(template, example):
    source = ROOT / example["file"]
    before = source.read_bytes()
    first = RENDERER.build_request(template["id"], example["scenario"])
    second = RENDERER.build_request(
        template["id"], example["scenario"], production=True
    )
    identity = template["identity_field"]
    assert first["body"][identity] != second["body"][identity]
    assert set(first["body"]) <= set(template["input_fields"])
    assert set(template["caller_required_fields"]) <= first["body"].keys()
    assert "/webhook-test/" in first["url"]
    assert "/webhook/" in second["url"]
    assert first["execution_performed"] is False
    if "customer_id" in first["body"]:
        assert first["body"]["customer_id"] != second["body"]["customer_id"]
    assert source.read_bytes() == before


def test_invalid_options_and_existing_output_do_not_silently_change_request(tmp_path):
    with pytest.raises(ValueError, match="Unknown template"):
        RENDERER.build_request("unknown")
    with pytest.raises(ValueError, match="Unknown scenario"):
        RENDERER.build_request("sales-followup", "unknown")
    with pytest.raises(ValueError, match="Base URL"):
        RENDERER.build_request("sales-followup", base_url="https://user:key@host")
    output = tmp_path / "request.json"
    output.write_text("keep this existing request", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(SCRIPT),
            "--template",
            "sales-followup",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert output.read_text(encoding="utf-8") == "keep this existing request"
