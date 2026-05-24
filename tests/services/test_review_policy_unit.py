import sys
from pathlib import Path
from typing import Any
import pytest
import hashlib
import json

# Force absolute imports for the test environment
ROOT = Path(r"C:\software\Holygrail\theFactory")
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

import orchestrator.review_policy as review_policy

def test_sanitize_review_text():
    text = "Hello\nWorld\r\0"
    sanitized = review_policy._sanitize_review_text(text, 10)
    assert "\n" not in sanitized
    assert "\r" not in sanitized
    assert "\0" not in sanitized
    assert sanitized == "Hello World"[:10]

def test_review_approval_id():
    scope = "mission"
    fingerprint = "abc123def456ghi7890123456789"
    approval_id = review_policy._review_approval_id(scope, fingerprint)
    assert approval_id.startswith("mission-approval-")
    assert approval_id.endswith(fingerprint[:24].lower())

def test_review_approval_digest():
    record = {"mission_id": "123", "action": "approve"}
    digest = review_policy._review_approval_digest(record)
    assert len(digest) == 64 # SHA-256
    
    # Determinism
    digest2 = review_policy._review_approval_digest(record)
    assert digest == digest2
    
    # Sort keys
    record_unsorted = {"action": "approve", "mission_id": "123"}
    digest3 = review_policy._review_approval_digest(record_unsorted)
    assert digest == digest3

def test_review_approval_record_path():
    approval_id = "test-id"
    path = review_policy._review_approval_record_path(approval_id)
    assert path == f"orchestrator://review-approvals/{approval_id}"
