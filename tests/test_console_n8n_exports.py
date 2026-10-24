"""Importable copies add correlation without altering frozen workflow logic."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "template,source",
    [
        ("customer-service", "w6d38-ai-customer-request"),
        ("email-assistant", "w6d41-persistent-ai-email-assistant"),
        ("sales-followup", "w7d47-sales-followup-assistant"),
    ],
)
def test_export_keeps_business_logic_and_binds_responses(template, source):
    original = json.loads(
        (ROOT / f"n8n/workflows/{source}.json").read_text(encoding="utf-8")
    )
    copied = json.loads(
        (ROOT / f"n8n/console/{template}.json").read_text(encoding="utf-8")
    )
    assert not copied["active"]
    assert "id" not in copied
    assert original["connections"] == copied["connections"]
    assert len(original["nodes"]) == len(copied["nodes"])
    for old, new in zip(original["nodes"], copied["nodes"], strict=True):
        assert old["name"] == new["name"]
        assert "credentials" not in new
        if new["type"] == "n8n-nodes-base.webhook":
            assert new["parameters"]["path"] == "console-" + template
        elif new["type"] == "n8n-nodes-base.respondToWebhook":
            body = new["parameters"]["responseBody"]
            assert "String($execution.id)" in body and "console_event_id:" in body
        else:
            assert old["parameters"] == new["parameters"]
