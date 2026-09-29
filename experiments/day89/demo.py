"""Offline transport demonstration with synthetic responses and fictional prices."""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/day64"))
from chat_tools import ChatTools, ToolChatError  # noqa: E402

from experiments.day87.runner import atomic_save  # noqa: E402
from experiments.day89.runner import replay  # noqa: E402
from experiments.day89.transport import UsageTransport  # noqa: E402


def demonstrate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    calls = 0

    def response(request):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise httpx.ReadTimeout("synthetic timeout")
        inputs, outputs = (100, 40) if calls == 1 else (50, 10)
        return httpx.Response(
            200,
            json=dict(
                model="demo-model",
                usage=dict(
                    prompt_tokens=inputs,
                    completion_tokens=outputs,
                    total_tokens=inputs + outputs,
                ),
                choices=[
                    dict(
                        finish_reason="stop",
                        message=dict(role="assistant", content="Fictional answer."),
                    )
                ],
            ),
        )

    meter = UsageTransport(
        httpx.MockTransport(response),
        provider="demo",
        model="demo-model",
        origin="synthetic_response",
    )
    config = SimpleNamespace(
        provider="demo",
        model="demo-model",
        base_url="https://example.invalid/v1",
        api_key="offline-placeholder",
    )
    chat = ChatTools(config_loader=lambda: config, transport=meter)
    prices = Path(__file__).with_name("examples") / "illustrative-pricing.json"
    for index in range(3):
        try:
            chat([dict(role="user", content="Fictional test input.")], [])
        except ToolChatError:
            if index != 2:
                raise
        if index == 1:
            atomic_save(
                output / "complete-ledger.json",
                [a.model_dump() for a in meter.attempts],
            )
    atomic_save(
        output / "partial-ledger.json", [a.model_dump() for a in meter.attempts]
    )
    replay(output / "complete-ledger.json", prices, output / "complete")
    replay(output / "partial-ledger.json", prices, output / "partial")
    atomic_save(
        output / "validation.json",
        dict(
            mode="synthetic_transport_demonstration",
            network_requests=0,
            synthetic_attempts=len(meter.attempts),
            real_model_requests=0,
            illustrative_prices=True,
        ),
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(demonstrate(args.output_dir))
