"""Inject a versioned system prompt without changing frozen agent code."""

import copy
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/day80"))
import hitl_agent as hitl  # noqa: E402

agent = hitl.agent
PROFILES = ("baseline", "candidate")


def prompt_text(profile):
    if profile == "baseline":
        return agent.SYSTEM
    if profile == "candidate":
        return Path(__file__).with_name("candidate.md").read_text(encoding="utf-8")
    raise ValueError("unknown_prompt_profile")


def identity(profile):
    text = prompt_text(profile).replace("\r\n", "\n")
    return {
        "profile": profile,
        "sha256_lf": hashlib.sha256(text.encode()).hexdigest(),
        "characters": len(text),
    }


class PromptChat:
    """Keep tools, tool_choice and response untouched; record actual inputs."""

    def __init__(self, chat, profile, suffix=""):
        self.chat = chat
        self.text = prompt_text(profile)
        self.identity = identity(profile)
        self.suffix = suffix
        self.inputs = []

    @property
    def requests(self):
        return getattr(self.chat, "requests", 0)

    @property
    def metadata(self):
        return dict(getattr(self.chat, "metadata", {}))

    def __call__(self, messages, tools, *, tool_choice="auto"):
        # Refuse an unexpected host contract instead of silently overwriting it.
        if (
            not isinstance(messages, list)
            or len(messages) < 2
            or messages[0] != {"role": "system", "content": agent.SYSTEM}
            or messages[1].get("role") != "user"
            or any(m.get("role") == "system" for m in messages[1:])
            or len(self.inputs) >= 4
        ):
            raise agent.ToolChatError("prompt_contract_invalid")
        forwarded = copy.deepcopy(messages)
        forwarded[0]["content"] = self.text
        forwarded[1]["content"] += self.suffix
        self.inputs.append(
            {"messages": copy.deepcopy(forwarded), "tool_choice": tool_choice}
        )
        return self.chat(forwarded, copy.deepcopy(tools), tool_choice=tool_choice)
