"""Structured JSON logging with request correlation IDs and sensitive data scrubbing."""

from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "authorization",
    "cookie",
    "session",
    "origin_lat",
    "origin_lon",
    "destination_lat",
    "destination_lon",
    "coordinates",
    "polyline",
)

_SENSITIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)(apikey|api_key|token|secret|password)=([^&\s\"']+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-+/=]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(x-spotter-session[:=]\s*)([^\s,;\"']+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(spotter_session=)([^;\s\"']+)"), r"\1[REDACTED]"),
)

_RESERVED_LOG_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
        "request_id",
    }
)


def get_request_id() -> str:
    """Return the active request correlation ID for the current execution context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> contextvars.Token[str]:
    """Bind a request correlation ID to the current execution context."""
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    """Restore the previous request correlation ID."""
    _request_id_var.reset(token)


def scrub_text(value: str) -> str:
    """Redact API keys, bearer tokens, and session tokens from arbitrary log text."""
    scrubbed = value
    for pattern, replacement in _SENSITIVE_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def scrub_value(key: str, value: Any) -> Any:
    """Redact values whose keys indicate secrets, tokens, or raw trip coordinates."""
    lowered = key.lower()
    if any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS):
        return "[REDACTED]"
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {str(k): scrub_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub_value(key, item) for item in value]
    return value


class RequestIDFilter(logging.Filter):
    """Inject the context-local request_id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id()
        return True


class StructuredJsonFormatter(logging.Formatter):
    """Emit compact single-line JSON logs with secret/PII scrubbing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", get_request_id()),
            "message": scrub_text(record.getMessage()),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_ATTRS or key.startswith("_"):
                continue
            payload[key] = scrub_value(key, value)

        if record.exc_info and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
            payload["exception"] = scrub_text(self.formatException(record.exc_info))

        return json.dumps(payload, default=str, ensure_ascii=True)
