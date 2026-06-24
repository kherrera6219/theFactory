"""Unit coverage for shared structured logging behavior."""
from __future__ import annotations

import json
import logging

from shared_runtime.logging_config import JsonFormatter, PiiRedactingFormatter


def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_redacts_messages_and_nested_extra_fields():
    formatter = JsonFormatter(service_name="test-service")
    record = _record(
        "Contact user@example.com at 555-867-5309",
        request={
            "owner": "admin@example.com",
            "credentials": {"password": "short-secret"},
        },
        authorization="Bearer short-token",
    )

    payload = json.loads(formatter.format(record))
    rendered = json.dumps(payload)

    assert "user@example.com" not in rendered
    assert "555-867-5309" not in rendered
    assert "admin@example.com" not in rendered
    assert "short-secret" not in rendered
    assert "short-token" not in rendered
    assert payload["request"]["credentials"]["password"] == "[REDACTED-CREDENTIAL]"
    assert payload["authorization"] == "[REDACTED-CREDENTIAL]"


def test_json_formatter_preserves_trace_correlation_fields():
    formatter = JsonFormatter(service_name="test-service")
    trace_id = "a" * 32
    span_id = "b" * 16
    record = _record("completed", trace_id=trace_id, span_id=span_id)

    payload = json.loads(formatter.format(record))

    assert payload["trace_id"] == trace_id
    assert payload["span_id"] == span_id


def test_plain_formatter_redacts_rendered_message():
    formatter = PiiRedactingFormatter("%(levelname)s %(message)s")

    rendered = formatter.format(_record("Contact user@example.com"))

    assert "user@example.com" not in rendered
    assert "[REDACTED-EMAIL]" in rendered
