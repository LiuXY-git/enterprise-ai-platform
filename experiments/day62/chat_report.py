"""Single bounded JSON-mode request, with no tool or automatic retry support."""

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
MAX_RESPONSE_BYTES = 131072


class ReportError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ChatReport:
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

    def __call__(self, messages: list[dict[str, str]]) -> str:
        try:
            config = self._config()
        except RuntimeError:
            raise ReportError("configuration_invalid") from None
        self.metadata = {"provider": config.provider, "model": config.model}
        body = {
            "model": config.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": 4096,
            "stream": False,
        }
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
                        raise ReportError(f"provider_http_{response.status_code}")
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise ReportError("response_too_large")
                        chunks.append(chunk)
                    payload = json.loads(b"".join(chunks))
        except httpx.TimeoutException:
            raise ReportError("provider_timeout") from None
        except httpx.RequestError:
            raise ReportError("provider_network_error") from None
        except (ValueError, UnicodeError, RecursionError):
            raise ReportError("provider_invalid_response") from None
        try:
            choice = payload["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ReportError("provider_incomplete_response")
            message = choice["message"]
            if message.get("tool_calls") or message.get("function_call"):
                raise ReportError("unexpected_tool_call")
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                raise ReportError("provider_empty_response")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ReportError("provider_invalid_response") from None
        return content
