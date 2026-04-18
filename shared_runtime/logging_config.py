"""Shared logging configuration.

Each service calls ``configure_logging(service_name)`` once at import time,
before uvicorn initializes its own loggers. The output format is controlled
by the ``LOG_FORMAT`` env var:

- ``plain`` (default): human-readable one-line-per-record output
- ``json``: one JSON object per record, suitable for log aggregators

Log level comes from ``LOG_LEVEL`` (default ``INFO``).

Stdlib-only — no new dependency.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime

_STANDARD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self._service_name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Surface any user-provided extra={} fields, but never overwrite core keys.
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key in payload:
                continue
            if key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(service_name: str) -> None:
    """Wire the root logger to stdout with either plain or JSON formatting.

    Safe to call multiple times; subsequent calls replace the root handler.
    """

    log_format = os.getenv("LOG_FORMAT", "plain").strip().lower()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter(service_name=service_name))
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(log_level)
