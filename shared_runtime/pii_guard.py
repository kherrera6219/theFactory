"""pii_guard.py — PII detection and redaction for theFactory.

2026 standard: OWASP LLM Top 10 requires PII detection at all API boundaries.
This module provides:
  - detect_pii()    → list of PII matches with type and position
  - redact_pii()    → replace PII with safe placeholders
  - scan_envelope() → validate an event envelope for PII leakage

Patterns are regex-based; no external API calls are made.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PiiMatch:
    """A single PII detection result."""

    pii_type: str
    start: int
    end: int
    placeholder: str


# ---------------------------------------------------------------------------
# PII pattern registry
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # (pii_type, compiled_pattern, placeholder)
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED-SSN]"),
    ("CREDIT_CARD", re.compile(r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13}|6011\d{12})\b"), "[REDACTED-CC]"),  # noqa: E501
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[REDACTED-EMAIL]"),  # noqa: E501
    ("PHONE_US", re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED-PHONE]"),  # noqa: E501
    ("PHONE_INTL", re.compile(r"\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{4,10}\b"), "[REDACTED-PHONE]"),
    ("JWT_TOKEN", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"), "[REDACTED-JWT]"),  # noqa: E501
    ("API_KEY_HEX", re.compile(r"\b[a-f0-9]{32,64}\b"), "[REDACTED-KEY]"),
    ("API_KEY_B64", re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"), "[REDACTED-KEY]"),
    ("PASSWORD_KV", re.compile(r"(?i)(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+"), "[REDACTED-CREDENTIAL]"),  # noqa: E501
    ("IP_ADDRESS", re.compile(r"\b(?:25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|\d{1,2})){3}\b"), "[REDACTED-IP]"),  # noqa: E501
]

# Fields that should NEVER be forwarded to LLM calls regardless of content
_FORBIDDEN_FORWARD_FIELDS = frozenset({"prompt", "source_code", "chain_trace"})
_MAX_CONTEXT_REDACTION_DEPTH = 12


def detect_pii(text: str) -> list[PiiMatch]:
    """Return all PII matches found in *text*, ordered by position."""
    if not text:
        return []
    matches: list[PiiMatch] = []
    for pii_type, pattern, placeholder in _PATTERNS:
        for m in pattern.finditer(text):
            matches.append(PiiMatch(
                pii_type=pii_type,
                start=m.start(),
                end=m.end(),
                placeholder=placeholder,
            ))
    # Sort by start position, longest match wins on overlap
    matches.sort(key=lambda m: (m.start, -(m.end - m.start)))
    return _deduplicate_matches(matches)


def _deduplicate_matches(matches: list[PiiMatch]) -> list[PiiMatch]:
    """Remove overlapping matches — keep the first (highest priority by pattern order)."""
    result: list[PiiMatch] = []
    last_end = -1
    for match in matches:
        if match.start >= last_end:
            result.append(match)
            last_end = match.end
    return result


def redact_pii(text: str) -> tuple[str, list[PiiMatch]]:
    """Replace all PII in *text* with safe placeholders.

    Returns:
        (redacted_text, list_of_matches)
    """
    matches = detect_pii(text)
    if not matches:
        return text, []
    parts: list[str] = []
    cursor = 0
    for match in matches:
        parts.append(text[cursor:match.start])
        parts.append(match.placeholder)
        cursor = match.end
    parts.append(text[cursor:])
    return "".join(parts), matches


def has_pii(text: str) -> bool:
    """Quick check — True if any PII pattern matches in *text*."""
    if not text:
        return False
    for _, pattern, _ in _PATTERNS:
        if pattern.search(text):
            return True
    return False


def scan_dict_for_pii(data: dict[str, Any], *, max_depth: int = 3) -> list[tuple[str, str]]:
    """Walk a dict and return (field_path, pii_type) for every PII hit.

    Used for scanning event envelope payloads before routing.
    """
    results: list[tuple[str, str]] = []
    _walk_dict(data, "", max_depth, results)
    return results


def _walk_dict(
    obj: Any,
    path: str,
    depth: int,
    results: list[tuple[str, str]],
) -> None:
    if depth <= 0:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else key
            _walk_dict(value, child_path, depth - 1, results)
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _walk_dict(item, f"{path}[{i}]", depth - 1, results)
    elif isinstance(obj, str):
        for match in detect_pii(obj):
            results.append((path, match.pii_type))


def safe_context_json_redact(context: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *context* with forbidden fields removed and remaining PII redacted.

    This is the 2026 standard pattern for safe LLM context forwarding:
    1. Strip fields that should never reach the LLM (prompt, source_code, chain_trace)
    2. Redact any PII remaining in allowed fields
    """
    return _redact_context_value(context, depth=0, seen=set())


def _redact_context_value(value: Any, *, depth: int, seen: set[int]) -> Any:
    if isinstance(value, str):
        redacted, _ = redact_pii(value)
        return redacted
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if depth >= _MAX_CONTEXT_REDACTION_DEPTH:
        return "[REDACTED-DEPTH-LIMIT]"

    if isinstance(value, dict):
        object_id = id(value)
        if object_id in seen:
            return "[REDACTED-CYCLE]"
        seen.add(object_id)
        try:
            return {
                str(key): _redact_context_value(item, depth=depth + 1, seen=seen)
                for key, item in value.items()
                if str(key) not in _FORBIDDEN_FORWARD_FIELDS
            }
        finally:
            seen.remove(object_id)

    if isinstance(value, (list, tuple)):
        object_id = id(value)
        if object_id in seen:
            return "[REDACTED-CYCLE]"
        seen.add(object_id)
        try:
            return [
                _redact_context_value(item, depth=depth + 1, seen=seen)
                for item in value
            ]
        finally:
            seen.remove(object_id)

    return _redact_context_value(str(value), depth=depth + 1, seen=seen)
