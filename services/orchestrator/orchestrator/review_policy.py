"""review_policy.py — Review-approval fingerprinting and sanitization helpers.

Pure functions with no I/O dependencies; safe to import from any layer.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

REVIEW_APPROVAL_STORAGE_BACKEND = "postgres"


def _sanitize_review_text(value: str, max_length: int) -> str:
    return (
        str(value)
        .replace("\u0000", "")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()[:max_length]
    )


def _review_approval_id(scope: str, fingerprint: str) -> str:
    return f"{scope}-approval-{fingerprint[:24].lower()}"


def _review_approval_digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _review_approval_record_path(approval_id: str) -> str:
    return f"orchestrator://review-approvals/{approval_id}"
