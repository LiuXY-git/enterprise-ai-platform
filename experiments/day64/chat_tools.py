"""Bounded, non-streaming tool protocol transport without automatic retries."""

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
MAX_RESPONSE_BYTES = 131072


class ToolChatError(Exception):
    """Expose a stable code without response text or configuration values."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ChatTools:
    def __init__(
        self, env_file: Path | None = None, *, config_loader=None, transport=None
    ):
        self.env_file = env_file
        self.config_loader = config_loader
        self.transport = transport
        self.requests = 0
        self.metadata = {}

    def _config(self):
        if self.config_loader is not None:
            return self.config_loader()
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from backend.app.settings import get_llm_config, load_environment

        load_environment(self.env_file)
        return get_llm_config()

    def __call__(
        self, messages: list[dict], tools: list[dict], *, tool_choice: str = "auto"
    ) -> dict:
        if tool_choice not in ("auto", "none"):
            raise ToolChatError("invalid_tool_choice")
        try:
            config = self._config()
        except RuntimeError:
            raise ToolChatError("configuration_invalid") from None
        self.metadata = {"provider": config.provider, "model": config.model}
        body = {
            "model": config.model,
            "messages": messages,
            "max_tokens": 1600,
            "stream": False,
        }
        if tools:
            body.update(tools=tools, tool_choice=tool_choice)
        if config.provider == "qwen":
            body["enable_thinking"] = False
        try:
            with httpx.Client(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                self.requests += 1
                with client.stream(
                    "POST",
                    config.base_url.rstrip("/") + "/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {config.api_key}"},
                ) as response:
                    if response.status_code != 200:
                        raise ToolChatError(f"provider_http_{response.status_code}")
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise ToolChatError("response_too_large")
                        chunks.append(chunk)
                    payload = json.loads(b"".join(chunks))
        except httpx.TimeoutException:
            raise ToolChatError("provider_timeout") from None
        except httpx.RequestError:
            raise ToolChatError("provider_network_error") from None
        except (ValueError, UnicodeError, RecursionError):
            raise ToolChatError("provider_invalid_response") from None
        if not isinstance(payload, dict):
            raise ToolChatError("provider_invalid_response")
        choices = payload.get("choices")
        if (
            not isinstance(choices, list)
            or len(choices) != 1
            or not isinstance(choices[0], dict)
        ):
            raise ToolChatError("provider_invalid_response")
        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        if finish_reason not in ("stop", "tool_calls"):
            raise ToolChatError("provider_incomplete_response")
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ToolChatError("provider_invalid_response")
        if message.get("function_call") is not None:
            raise ToolChatError("legacy_function_call")
        normalized = {
            key: message[key]
            for key in ("role", "content", "tool_calls")
            if key in message
        }
        calls = normalized.get("tool_calls")
        if isinstance(calls, list):
            normalized_calls = []
            for call in calls:
                if isinstance(call, dict) and "index" in call:
                    # Qwen also includes this position metadata in full responses.
                    # Preserve all other fields for the core's strict validation.
                    if type(call["index"]) is not int or call["index"] < 0:
                        raise ToolChatError("provider_invalid_response")
                    call = {key: value for key, value in call.items() if key != "index"}
                normalized_calls.append(call)
            normalized["tool_calls"] = normalized_calls
        return {"message": normalized, "finish_reason": finish_reason}
