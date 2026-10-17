"""Bounded, fixture-only child task; no model, network, tool or notification."""

import json
import sys

from .contracts import SmokeInput


def main():
    request = SmokeInput.model_validate(json.loads(sys.stdin.read(2048)))
    print(
        json.dumps({"echo": request.message, "external_calls": 0}, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
