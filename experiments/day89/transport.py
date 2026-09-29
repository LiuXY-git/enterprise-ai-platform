"""Bounded usage-only observer around an injected synchronous HTTP transport."""

import json

import httpx

from experiments.day86.dataset_tool import reject_constant, unique_object
from experiments.day89.usage import Attempt, parse_usage

MAX_BYTES = 131072


class UsageStream(httpx.SyncByteStream):
    def __init__(self, stream, finish):
        self.stream, self.finish = stream, finish
        self.parts = []
        self.size = 0
        self.complete = False
        self.closed = False

    def __iter__(self):
        for chunk in self.stream:
            self.size += len(chunk)
            if self.size <= MAX_BYTES:
                self.parts.append(chunk)
            else:
                self.parts.clear()
            yield chunk
        self.complete = True

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.stream.close()
        finally:
            payload = None
            if self.complete and self.size <= MAX_BYTES:
                try:
                    payload = json.loads(
                        b"".join(self.parts),
                        object_pairs_hook=unique_object,
                        parse_constant=reject_constant,
                    )
                except (ValueError, UnicodeError, RecursionError):
                    pass
            self.finish(payload, self.complete)
            self.parts.clear()


class UsageTransport(httpx.BaseTransport):
    """Caller supplies transport and declared provider/model; no network by default.

    Ledger records only usage/status/identity, never headers, messages or body.
    One transport instance observes sequential attempts. It does not add retries.
    """

    def __init__(self, inner, *, provider, model, origin="provider_response"):
        self.inner, self.provider, self.model, self.origin = (
            inner,
            provider,
            model,
            origin,
        )
        self.attempts = []

    def handle_request(self, request):
        identity_ok = False
        try:
            body = json.loads(request.content)
            identity_ok = (
                body.get("model") == self.model and body.get("stream") is False
            )
        except (ValueError, TypeError, AttributeError):
            pass
        attempt_id = len(self.attempts) + 1

        def finish(payload, complete):
            usage = parse_usage(payload) if complete else parse_usage(None)
            if not identity_ok or (
                isinstance(payload, dict)
                and payload.get("model", self.model) != self.model
            ):
                usage["flat_pricing_supported"] = False
            self.attempts.append(
                Attempt(
                    attempt_id=attempt_id,
                    provider=self.provider,
                    model=self.model,
                    origin=self.origin,
                    outcome="response" if complete else "incomplete_response",
                    http_status=response.status_code,
                    **usage,
                )
            )

        try:
            response = self.inner.handle_request(request)
        except Exception:
            self.attempts.append(
                Attempt(
                    attempt_id=attempt_id,
                    provider=self.provider,
                    model=self.model,
                    origin=self.origin,
                    outcome="transport_error",
                    http_status=None,
                    **parse_usage(None),
                )
            )
            raise
        if response.is_stream_consumed:
            payload = None
            if len(response.content) <= MAX_BYTES:
                try:
                    payload = json.loads(
                        response.content,
                        object_pairs_hook=unique_object,
                        parse_constant=reject_constant,
                    )
                except (ValueError, UnicodeError, RecursionError):
                    pass
            finish(payload, True)
            return response
        response.stream = UsageStream(response.stream, finish)
        return response

    def close(self):
        self.inner.close()
