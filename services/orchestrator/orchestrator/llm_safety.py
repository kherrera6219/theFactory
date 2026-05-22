"""llm_safety.py — Centralized safety checks for all LLM entry and exit paths.

Provides outbound prompt scanning (blocks secrets and PII from reaching
the model) and inbound response scanning (flags prompt injection attempts
in model output).

All functions are pure and synchronous — no I/O, no side effects.
They are called from _call_with_recommendation() in llm_delegation.py.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Outbound patterns — things that must never be sent to an LLM
# ---------------------------------------------------------------------------
_OUTBOUND_BLOCK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key_sk",       re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE)),
    ("github_token_ghp", re.compile(r"ghp_[A-Za-z0-9]{20,}", re.IGNORECASE)),
    ("github_pat",       re.compile(r"github_pat_[A-Za-z0-9_]{20,}", re.IGNORECASE)),
    ("ssn_pattern",      re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("visa_card",        re.compile(r"\b4[0-9]{12}(?:[0-9]{3})?\b")),
    ("mastercard",       re.compile(r"\b5[1-5][0-9]{14}\b")),
]

# ---------------------------------------------------------------------------
# Inbound patterns — injection indicators in model responses
# ---------------------------------------------------------------------------
_INBOUND_FLAG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions", re.compile(r"IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS", re.IGNORECASE)),
    ("dan_jailbreak",       re.compile(r"You\s+are\s+now\s+DAN", re.IGNORECASE)),
    ("system_override",     re.compile(r"system\s*:\s*(you\s+are|ignore)", re.IGNORECASE)),
    ("im_start_inject",     re.compile(r"<\|im_start\|>\s*system", re.IGNORECASE)),
    ("role_override",       re.compile(
        r"forget\s+your\s+(previous\s+)?instructions", re.IGNORECASE
    )),
]


def check_outbound_prompt(prompt: str, call_context: str) -> list[str]:
    """Return a list of violation descriptions found in an outbound prompt.

    An empty list means the prompt is safe to send.
    """
    violations: list[str] = []
    for name, pattern in _OUTBOUND_BLOCK_PATTERNS:
        if pattern.search(prompt):
            violations.append(
                f"outbound_safety:{name} detected in prompt for {call_context!r}"
            )
    return violations


def check_inbound_response(text: str, call_context: str) -> list[str]:
    """Return a list of safety flag descriptions found in model response text."""
    flags: list[str] = []
    for name, pattern in _INBOUND_FLAG_PATTERNS:
        if pattern.search(text):
            flags.append(
                f"inbound_safety:{name} detected in response from {call_context!r}"
            )
    return flags


def sanitize_outbound_prompt(prompt: str) -> str:
    """Redact known sensitive patterns from an outbound prompt.

    Used when LLM_SAFETY_BLOCK_ENABLED=false (log-only mode) to
    sanitize rather than block.
    """
    result = prompt
    for _name, pattern in _OUTBOUND_BLOCK_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
