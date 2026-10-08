"""Trace outside FastAPI's error middleware, including generated 500 responses."""

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI

from ..observability import request_id_context

logger = logging.getLogger("enterprise_ai_platform.http")


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid4().hex
        # Always server-generated; inbound IDs are untrusted and never logged.
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started = perf_counter()
        status = None
        complete = False
        error_type = None

        async def traced_send(message):
            nonlocal status, complete
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                complete = True

        try:
            await self.app(scope, receive, traced_send)
        except BaseException as exc:
            error_type = type(exc).__name__
            raise
        finally:
            try:
                failed = (
                    error_type is not None
                    or not complete
                    or status is None
                    or status >= 500
                )
                level = (
                    logging.ERROR
                    if failed
                    else logging.WARNING
                    if status >= 400
                    else logging.INFO
                )
                logger.log(
                    level,
                    "http_request_failed" if failed else "http_request_completed",
                    extra={
                        "method": scope.get("method"),
                        "route": getattr(scope.get("route"), "path", None),
                        "status_code": status,
                        "duration_ms": (perf_counter() - started) * 1000,
                        "response_complete": complete,
                        "error_type": error_type,
                    },
                )
            except Exception:
                # Observation must not change an already executed operation.
                pass
            finally:
                request_id_context.reset(token)


class LoggedFastAPI(FastAPI):
    def build_middleware_stack(self):
        # Wrap the framework's complete stack without replacing its error handling.
        # Construction remains lazy; callers may still add routes/middleware.
        return RequestLoggingMiddleware(super().build_middleware_stack())
