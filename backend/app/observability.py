"""Metadata-only application logs and request-scoped correlation."""

import json
import logging
import math
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

SERVICE = "enterprise-ai-platform-api"
request_id_context = ContextVar("request_id", default=None)
# Only fixed, reviewed templates become events. Arguments and exception text
# are intentionally never formatted: URLs, filenames and bodies may be private.
EVENTS = {
    "正在启动 Enterprise AI Platform": "application_starting",
    "数据库初始化失败": "database_initialization_failed",
    "数据库初始化成功": "database_initialized",
    "Enterprise AI Platform 已停止": "application_stopped",
    "收到上传请求：filename=%s, content_type=%s": "upload_received",
    "上传失败：文件名为空": "upload_filename_missing",
    "读取上传文件失败：filename=%s": "upload_read_failed",
    "上传失败：文件内容为空，filename=%s": "upload_empty",
    "上传失败：不支持的文件类型，filename=%s, content_type=%s": "upload_type_rejected",
    "文档解析失败：filename=%s, error=%s": "document_parse_failed",
    "处理文档时发生服务器错误：filename=%s": "document_processing_failed",
    "文档处理成功：document_id=%s, filename=%s, file_type=%s, chunk_count=%s": "document_indexed",
    "飞书消息请求失败 attempt=%s/%s reason=%s": "feishu_request_failed",
    "飞书消息准备重试 wait_seconds=%s": "feishu_retry_wait",
    "飞书消息接口返回了无效 JSON": "feishu_invalid_json",
    "飞书消息响应校验失败 reason=%s": "feishu_invalid_response",
    "飞书消息发送成功 attempts=%s": "feishu_message_sent",
    "workflow_event_logging_failed": "workflow_event_logging_failed",
    "workflow_event_build_failed": "workflow_event_build_failed",
    "http_request_completed": "http_request_completed",
    "http_request_failed": "http_request_failed",
}
METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
    "TRACE",
    "CONNECT",
}


def current_request_id():
    value = request_id_context.get()
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value)
        else None
    )


def identifier(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_.]{1,128}", value)
        else "unknown"
    )


class JsonFormatter(logging.Formatter):
    def format(self, record):
        event = (
            EVENTS.get(record.msg, "application_log")
            if isinstance(record.msg, str)
            else "application_log"
        )
        result = {
            "schema_version": 1,
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "service": SERVICE,
            "level": record.levelname
            if record.levelname in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            else "UNKNOWN",
            "logger": identifier(record.name),
            "event": event,
            "request_id": current_request_id(),
            "source": {"module": identifier(record.module), "line": record.lineno},
        }
        error_type = getattr(record, "error_type", None)
        if record.exc_info and record.exc_info[0]:
            error_type = record.exc_info[0].__name__
        if error_type is not None:
            result["error_type"] = identifier(error_type)
        if event in {"http_request_completed", "http_request_failed"}:
            method = getattr(record, "method", None)
            result["method"] = method if method in METHODS else "OTHER"
            # This field is the route template supplied by the middleware,
            # never scope['path'] or the query string.
            route = getattr(record, "route", None)
            result["route"] = (
                route
                if isinstance(route, str)
                and re.fullmatch(r"[/a-zA-Z0-9_{}:.-]{1,256}", route)
                else "unmatched"
            )
            status = getattr(record, "status_code", None)
            result["status_code"] = (
                status if type(status) is int and 100 <= status <= 599 else None
            )
            duration = getattr(record, "duration_ms", None)
            result["duration_ms"] = (
                round(duration, 3)
                if type(duration) in (int, float)
                and math.isfinite(duration)
                and duration >= 0
                else None
            )
            result["response_complete"] = (
                getattr(record, "response_complete", False) is True
            )
        return json.dumps(result, ensure_ascii=False, allow_nan=False)


def sink_failure():
    # logging.Handler.handleError normally dumps record arguments/tracebacks.
    # Use a fixed message even when the destination is full or unavailable.
    try:
        sys.stderr.write(
            '{"event":"log_sink_failed","level":"ERROR","service":"enterprise-ai-platform-api"}\n'
        )
    except Exception:
        pass


class SafeRotatingFileHandler(RotatingFileHandler):
    def handleError(self, record):
        sink_failure()


class SafeConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        self.stream = sys.stderr
        super().emit(record)

    def handleError(self, record):
        sink_failure()


def configure_server_logging(formatter):
    """Replace raw server access/exception output after application startup."""
    server = logging.getLogger("uvicorn")
    owned = [h for h in server.handlers if isinstance(h, SafeConsoleHandler)]
    if not owned:
        owned = [SafeConsoleHandler()]
    owned[0].setFormatter(formatter)
    server.handlers = owned[:1]
    server.propagate = False
    errors = logging.getLogger("uvicorn.error")
    errors.handlers = []
    errors.propagate = True
    # The platform request event replaces access lines containing raw URLs.
    # Client transport logs can also include credential-bearing URLs.
    for name in ("uvicorn.access", "httpx", "httpcore"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        logger.disabled = True
