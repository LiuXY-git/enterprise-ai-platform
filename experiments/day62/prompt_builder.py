"""Keep policy/schema in the system message and untrusted snapshots in user data."""

import hashlib
import json
from pathlib import Path

from report_contract import ReportDecision, ScenarioInput

PROMPT_VERSION = "day62-sales-report-v1"
MAX_INPUT_CHARS = 16000


def system_prompt() -> str:
    rules = Path(__file__).with_name("system-prompt.md").read_text(encoding="utf-8")
    schema = json.dumps(
        ReportDecision.model_json_schema(), ensure_ascii=False, sort_keys=True
    )
    return rules.replace("\r\n", "\n").rstrip() + "\n\nJSON Schema:\n" + schema


def prompt_hash() -> str:
    return hashlib.sha256(system_prompt().encode("utf-8")).hexdigest()


def build_messages(source: ScenarioInput) -> list[dict[str, str]]:
    data = json.dumps(source.model_dump(), ensure_ascii=False, sort_keys=True)
    if len(data) > MAX_INPUT_CHARS:
        raise ValueError("input_too_large")
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": data},
    ]
