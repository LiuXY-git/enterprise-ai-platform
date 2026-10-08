"""Bounded, best-effort observability for the workflow HTTP boundary."""

import inspect
import json
import logging
import math
import re
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .observability import (
    SERVICE,
    SafeConsoleHandler,
    SafeRotatingFileHandler,
    current_request_id,
)

EVENT_LOGGER = "enterprise_ai_platform.workflow_events"
SECRET_KEYS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "apikey",
    "token",
    "accesstoken",
    "refreshtoken",
    "clientsecret",
}
PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/-]+=*"),
    re.compile(r"sk-[a-zA-Z0-9_-]{8,}"),
    re.compile(
        r"""(?i)(?:api[_-]?key|password|secret|token)\s*[=:]\s*["']?[^\s,;"']+"""
    ),
)


def _text(value: str) -> str:
    for pattern in PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value[:1000] + ("[TRUNCATED]" if len(value) > 1000 else "")


def snapshot(value):
    """Create a limited copy; never change a response or the persisted payload."""
    remaining = 100

    def visit(item, depth=0):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 5:
            return "[TRUNCATED]"
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if remaining <= 0:
                    result["__truncated__"] = True
                    break
                safe_key = _text(str(key))
                normalized = re.sub(r"[^a-z]", "", str(key).lower())
                result[safe_key] = (
                    "[REDACTED]"
                    if normalized in SECRET_KEYS
                    else visit(child, depth + 1)
                )
            return result
        if isinstance(item, list):
            result = []
            for child in item:
                if remaining <= 0:
                    result.append("[TRUNCATED]")
                    break
                result.append(visit(child, depth + 1))
            return result
        if isinstance(item, str):
            return _text(item)
        if isinstance(item, float) and not math.isfinite(item):
            return "[NON_FINITE_NUMBER]"
        if item is None or isinstance(item, (bool, int, float)):
            return item
        return "[UNSUPPORTED]"

    result = visit(value)
    serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
    if len(serialized) > 8000:
        return {"truncated": True, "preview": serialized[:8000]}
    return result


def configure_workflow_logging(directory: Path) -> None:
    logger = logging.getLogger(EVENT_LOGGER)
    if logger.handlers:
        return
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(message)s")
    file_handler = SafeRotatingFileHandler(
        directory / "workflow-events.jsonl",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console = SafeConsoleHandler()
    console.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def emit_event(event: dict) -> None:
    """Logging must not turn a committed business operation into an HTTP failure."""
    try:
        logging.getLogger(EVENT_LOGGER).info(
            json.dumps(
                {key: snapshot(value) for key, value in event.items()},
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    except Exception:
        # No payload or raw exception text is sent to the fallback logger.
        try:
            logging.getLogger("enterprise_ai_platform").warning(
                "workflow_event_logging_failed"
            )
        except Exception:
            pass


def _record(operation, arguments, response, error, started):
    try:
        request = arguments.get("request")
        body = request.model_dump(mode="json") if request is not None else {}
        result = response.model_dump(mode="json") if response is not None else {}
        is_dify = operation == "dify.call"
        outcome = "error" if error is not None else "success"
        if result.get("duplicate"):
            outcome = "duplicate"
        elif result.get("replayed"):
            outcome = "replayed"
        input_data = (
            {"question": body.get("question"), "user": body.get("user")}
            if is_dify
            else result.get("input_data", body.get("input_data"))
        )
        output_data = (
            {"answer": result.get("answer"), "outputs": result.get("outputs")}
            if is_dify and error is None
            else result.get("output_data")
        )
        if operation == "workflow.checkpoint":
            output_data = result.get("checkpoint_data")
        has_metrics = any(
            result.get(k) is not None for k in ("elapsed_time", "total_tokens")
        )
        metrics_source = (
            "dify_response"
            if is_dify and has_metrics
            else "workflow_client_reported"
            if operation == "workflow.finish" and has_metrics
            else "not_reported"
        )
        # Stored metrics on a duplicate/failed record are not fresh model usage.
        fresh_metrics = operation in {"dify.call", "workflow.finish"} and error is None
        event = {
            "schema_version": 1,
            "service": SERVICE,
            "level": "ERROR" if error else "INFO",
            "request_id": current_request_id(),
            "timestamp": datetime.now(UTC).isoformat(),
            "log_event_id": str(uuid4()),
            "operation": operation,
            "outcome": outcome,
            "http_status": getattr(error, "status_code", 500) if error else 200,
            "status": result.get("status"),
            "run_id": None
            if is_dify
            else result.get("run_id", arguments.get("run_id")),
            "dify_run_id": result.get("workflow_run_id") if is_dify else None,
            "event_id": result.get("event_id", body.get("event_id")),
            "workflow_name": "dify-workflow"
            if is_dify
            else result.get("workflow_name", body.get("workflow_name")),
            "n8n_execution_id": result.get(
                "n8n_execution_id", arguments.get("n8n_execution_id")
            ),
            "request_n8n_execution_id": body.get("n8n_execution_id"),
            "retry_count": result.get("retry_count"),
            "duplicate_count": result.get("duplicate_count"),
            "processing_stage": result.get("processing_stage"),
            "failure_stage": result.get("failure_stage"),
            "error_type": type(error).__name__ if error else result.get("error_type"),
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "elapsed_time_seconds": result.get("elapsed_time")
            if fresh_metrics
            else None,
            "total_tokens": result.get("total_tokens") if fresh_metrics else None,
            "metrics_source": metrics_source,
            "input": snapshot(input_data),
            "output": snapshot(output_data),
            "snapshot_policy": "redacted_bounded_v1",
        }
        emit_event(event)
    except Exception:
        # Instrumentation cannot change endpoint results, including logging errors.
        try:
            logging.getLogger("enterprise_ai_platform").warning(
                "workflow_event_build_failed"
            )
        except Exception:
            pass


def observe_workflow(operation: str):
    """Observe validated route calls, preserving signatures and response contracts."""

    def decorate(function):
        signature = inspect.signature(function)

        def arguments(args, kwargs):
            return signature.bind(*args, **kwargs).arguments

        if inspect.iscoroutinefunction(function):

            @wraps(function)
            async def async_wrapper(*args, **kwargs):
                started = perf_counter()
                response, error = None, None
                try:
                    response = await function(*args, **kwargs)
                    return response
                except Exception as exc:
                    error = exc
                    raise
                finally:
                    _record(
                        operation, arguments(args, kwargs), response, error, started
                    )

            return async_wrapper

        @wraps(function)
        def wrapper(*args, **kwargs):
            started = perf_counter()
            response, error = None, None
            try:
                response = function(*args, **kwargs)
                return response
            except Exception as exc:
                error = exc
                raise
            finally:
                _record(operation, arguments(args, kwargs), response, error, started)

        return wrapper

    return decorate
