"""Render a fresh example request locally; never execute a workflow."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "n8n/templates/catalog.json"


def build_request(
    template_id: str,
    scenario: str | None = None,
    base_url: str = "http://localhost:5678",
    production: bool = False,
) -> dict:
    """Return an envelope, preserving the tracked example and workflow exports."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    template = next(
        (item for item in catalog["templates"] if item["id"] == template_id), None
    )
    if template is None:
        raise ValueError(f"Unknown template: {template_id}")
    scenario = scenario or template["examples"][0]["scenario"]
    example = next(
        (item for item in template["examples"] if item["scenario"] == scenario), None
    )
    if example is None:
        raise ValueError(f"Unknown scenario for {template_id}: {scenario}")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Base URL must use http(s), without credentials/query/fragment"
        )
    body = json.loads((REPO_ROOT / example["file"]).read_text(encoding="utf-8"))
    suffix = uuid4().hex
    body[template["identity_field"]] = f"day50-{template_id}-{suffix}"
    if "customer_id" in body:
        body["customer_id"] = f"demo-customer-{suffix}"
    if "report_date" in body:
        body["report_date"] = (
            datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        )
    endpoint = "webhook" if production else "webhook-test"
    url = f"{base_url.rstrip('/')}/{endpoint}/{template['webhook_path']}"
    if template_id != "sales-followup":
        url += "?" + urlencode({"channel": "template-demo"})
    return {
        "template_id": template_id,
        "scenario": scenario,
        "execution_performed": False,
        "method": "POST",
        "url": url,
        "headers": {
            "Content-Type": "application/json",
            "X-Client-Name": "day50-template-demo",
        },
        "body": body,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    parser.add_argument("--scenario")
    parser.add_argument("--base-url", default="http://localhost:5678")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        request = build_request(
            args.template, args.scenario, args.base_url, args.production
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Request saved: {args.output.resolve()}")
    print("No HTTP request, model call, CRM write, or message sending performed.")


if __name__ == "__main__":
    main()
