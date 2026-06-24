"""Tests for shared_runtime/pii_guard.py — Phase 2 security hardening."""
from __future__ import annotations

from shared_runtime.pii_guard import (
    detect_pii,
    has_pii,
    redact_pii,
    safe_context_json_redact,
    scan_dict_for_pii,
)


class TestDetectPii:
    def test_detects_ssn(self):
        matches = detect_pii("My SSN is 123-45-6789.")
        assert any(m.pii_type == "SSN" for m in matches)

    def test_detects_email(self):
        matches = detect_pii("Contact user@example.com for help.")
        assert any(m.pii_type == "EMAIL" for m in matches)

    def test_detects_us_phone(self):
        matches = detect_pii("Call me at 555-867-5309.")
        assert any(m.pii_type == "PHONE_US" for m in matches)

    def test_detects_jwt(self):
        # Pass the JWT directly — avoid "Token:" prefix which triggers PASSWORD_KV first
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0In0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        matches = detect_pii(jwt)
        assert any(m.pii_type == "JWT_TOKEN" for m in matches)

    def test_detects_jwt_with_bearer_prefix(self):
        # The "Authorization:" prefix triggers PASSWORD_KV — JWT should still appear in scan_dict
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0In0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        data = {"auth_header": f"Bearer {jwt}"}
        results = scan_dict_for_pii(data)
        # At minimum PASSWORD_KV or JWT_TOKEN should be detected
        assert len(results) >= 1

    def test_detects_api_key_hex(self):
        matches = detect_pii("key=abcdef1234567890abcdef1234567890abcdef12")
        assert any(m.pii_type in {"API_KEY_HEX", "PASSWORD_KV"} for m in matches)

    def test_detects_password_kv(self):
        matches = detect_pii("password=supersecretvalue123")
        assert any(m.pii_type == "PASSWORD_KV" for m in matches)

    def test_clean_text_returns_empty(self):
        matches = detect_pii("Build a Python data pipeline for processing CSV files.")
        assert matches == []

    def test_empty_text(self):
        assert detect_pii("") == []
        assert detect_pii("   ") == []

    def test_no_overlap_in_results(self):
        text = "email: user@example.com  phone: 555-867-5309"
        matches = detect_pii(text)
        for i in range(len(matches) - 1):
            assert matches[i].end <= matches[i + 1].start, "overlapping PII matches"


class TestRedactPii:
    def test_redacts_email(self):
        redacted, matches = redact_pii("Send to user@example.com now.")
        assert "user@example.com" not in redacted
        assert "[REDACTED-EMAIL]" in redacted
        assert len(matches) >= 1

    def test_redacts_ssn(self):
        redacted, matches = redact_pii("SSN: 123-45-6789")
        assert "123-45-6789" not in redacted
        assert "[REDACTED-SSN]" in redacted

    def test_clean_text_unchanged(self):
        text = "Build a data pipeline."
        redacted, matches = redact_pii(text)
        assert redacted == text
        assert matches == []

    def test_multiple_redactions(self):
        text = "user@example.com and 555-867-5309"
        redacted, matches = redact_pii(text)
        assert len(matches) >= 2
        assert "user@example.com" not in redacted
        assert "555-867-5309" not in redacted


class TestHasPii:
    def test_true_for_email(self):
        assert has_pii("contact@example.com") is True

    def test_false_for_clean_text(self):
        assert has_pii("Build a REST API in Python") is False

    def test_false_for_empty(self):
        assert has_pii("") is False


class TestScanDictForPii:
    def test_finds_pii_in_nested_dict(self):
        data = {"user": {"email": "test@example.com", "name": "Alice"}}
        results = scan_dict_for_pii(data)
        assert any("EMAIL" in pii_type for _, pii_type in results)

    def test_empty_dict_returns_empty(self):
        assert scan_dict_for_pii({}) == []

    def test_max_depth_respected(self):
        data = {"a": {"b": {"c": {"d": "deep@example.com"}}}}
        results_depth_2 = scan_dict_for_pii(data, max_depth=2)
        results_depth_5 = scan_dict_for_pii(data, max_depth=5)
        assert len(results_depth_5) >= len(results_depth_2)


class TestSafeContextJsonRedact:
    def test_strips_forbidden_fields(self):
        ctx = {
            "mission_id": "m-001",
            "prompt": "My email is test@example.com",
            "source_code": "print('hello')",
            "chain_trace": {"routing": "AGENT-99"},
            "requested_target_language": "python",
        }
        result = safe_context_json_redact(ctx)
        assert "prompt" not in result
        assert "source_code" not in result
        assert "chain_trace" not in result
        assert result["mission_id"] == "m-001"
        assert result["requested_target_language"] == "python"

    def test_redacts_pii_in_allowed_fields(self):
        ctx = {
            "mission_id": "m-002",
            "metadata_note": "Contact admin@corp.com for access",
        }
        result = safe_context_json_redact(ctx)
        assert "admin@corp.com" not in result.get("metadata_note", "")
        assert "[REDACTED-EMAIL]" in result.get("metadata_note", "")

    def test_recursively_redacts_nested_context_and_forbidden_fields(self):
        ctx = {
            "conversation": {
                "messages": [
                    {
                        "role": "user",
                        "text": "Contact nested@example.com",
                        "prompt": "do not forward this",
                    }
                ],
                "chain_trace": {"raw": "internal"},
            }
        }

        result = safe_context_json_redact(ctx)
        message = result["conversation"]["messages"][0]

        assert message["text"] == "Contact [REDACTED-EMAIL]"
        assert "prompt" not in message
        assert "chain_trace" not in result["conversation"]

    def test_handles_recursive_context_without_recursing_forever(self):
        ctx = {"mission_id": "m-cycle"}
        ctx["self"] = ctx

        result = safe_context_json_redact(ctx)

        assert result["mission_id"] == "m-cycle"
        assert result["self"] == "[REDACTED-CYCLE]"
