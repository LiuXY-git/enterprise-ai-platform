"""Prepare an offline recording bundle from existing workflow templates."""

import argparse
import copy
import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "day50_renderer", ROOT / "scripts/day50/render_template_request.py"
)
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)

STEPS = (
    ("01-customer", "customer-service", "question"),
    ("02-email-review", "email-assistant", "human-review"),
    ("03-sales", "sales-followup", "normal"),
)


def encode(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def prepare_bundle(
    output_dir: Path,
    *,
    n8n_base_url: str = "http://localhost:5678",
    production: bool = False,
) -> dict:
    """Create a new directory; never send requests or overwrite an old session."""
    output_dir = Path(output_dir)
    batch_id = uuid4().hex
    requests = {}
    for step, template, scenario in STEPS:
        request = RENDERER.build_request(template, scenario, n8n_base_url, production)
        identity = "request_id" if template == "customer-service" else "event_id"
        request["body"][identity] = f"day55-{template}-{batch_id}"
        if "customer_id" in request["body"]:
            request["body"]["customer_id"] = f"day55-{template}-customer-{batch_id}"
        request["headers"]["X-Client-Name"] = "day55-recording-demo"
        requests[step] = request

    # A duplicate demonstration must preserve the exact original business input.
    requests["04-sales-duplicate"] = copy.deepcopy(requests["03-sales"])
    files = {f"{step}.request.json": encode(req) for step, req in requests.items()}
    steps = []
    for step, request in requests.items():
        filename = f"{step}.request.json"
        steps.append(
            {
                "step": step,
                "request_file": filename,
                "sha256": hashlib.sha256(files[filename].encode("utf-8")).hexdigest(),
                "template_id": request["template_id"],
                "scenario": request["scenario"],
                "url": request["url"],
                "request_or_event_id": request["body"].get(
                    "event_id", request["body"].get("request_id")
                ),
                "duplicate_of": "03-sales" if step == "04-sales-duplicate" else None,
            }
        )
    manifest = {
        "schema_version": 1,
        "batch_id": batch_id,
        "prepared_at": datetime.now(UTC).isoformat(),
        "status": "prepared_not_executed",
        "webhook_mode": "production" if production else "test",
        "execution_performed": False,
        "video_recorded": False,
        "steps": steps,
        "notice": (
            "This manifest describes preparation only. Requests have not been sent. "
            "Record actual execution and video review separately in recording-notes.json."
        ),
    }
    notes = {
        "schema_version": 1,
        "batch_id": batch_id,
        "status": "not_recorded",
        "recorded_at": None,
        "video": {"filename": None, "duration_seconds": None, "sha256": None},
        "runs": {
            "customer_dify_run_id": None,
            "email_platform_run_id": None,
            "sales_platform_run_id": None,
            "sales_followup_id": None,
        },
        "checks": {
            "customer_answer_supported_by_knowledge": None,
            "email_review_persisted_without_draft": None,
            "sales_crm_saved_with_preview_and_zero_attempts": None,
            "duplicate_kept_same_run_and_single_followup": None,
            "video_audio_and_text_readable": None,
            "video_contains_no_credentials_or_real_customer_data": None,
        },
        "evidence_files": [],
        "issues": [],
        "notice": "Null means not checked. Fill only from this session's evidence.",
    }
    files["manifest.json"] = encode(manifest)
    files["recording-notes.json"] = encode(notes)

    # Validate every request before creating any output; retain partial files on I/O
    # failure so the operator can inspect them, never erase or overwrite a session.
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        with (output_dir / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--n8n-base-url", default="http://localhost:5678")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    try:
        manifest = prepare_bundle(
            args.output_dir,
            n8n_base_url=args.n8n_base_url,
            production=args.production,
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Demo bundle: {args.output_dir.resolve()}")
    print(f"Batch: {manifest['batch_id']} ({manifest['webhook_mode']} URLs)")
    print("Prepared 4 requests, a manifest and unfilled recording notes.")
    print("No HTTP requests, model calls, CRM writes or message sending performed.")


if __name__ == "__main__":
    main()
