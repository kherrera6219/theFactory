"""
test_api_contracts.py
=====================
Contract tests for the orchestrator HTTP API.

These tests validate that every error response conforms to the normalised
error envelope introduced in Phase 5::

    {
        "error": "<machine-readable type>",
        "detail": "<human-readable message or validation errors list>",
        "correlation_id": "<opaque string>"
    }

They also validate the review approval CRUD shape (create, retrieve, TTL
expiry) and common success/error response shapes for mission endpoints.

All tests run in-process via FastAPI's TestClient — no live services required.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

import orchestrator.main as orchestrator_main  # noqa: E402
from orchestrator import storage  # noqa: E402
from orchestrator.auth import AuthContext  # noqa: E402
from orchestrator.main import app as orch_app  # noqa: E402
from orchestrator.models import MissionRecord, MissionState  # noqa: E402
from orchestrator.settings import Settings  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _override_auth():
    """Bypass auth for all contract tests — we test auth separately."""
    orch_app.dependency_overrides[orchestrator_main.INTERNAL_AUTH] = (
        lambda: AuthContext(
            api_key="test-internal-key",
            roles={"internal", "worker", "mutate", "read"},
        )
    )
    orch_app.dependency_overrides[orchestrator_main.MUTATION_AUTH] = (
        lambda: AuthContext(
            api_key="test-mutate-key",
            roles={"admin", "mutate", "read"},
        )
    )
    yield
    orch_app.dependency_overrides.clear()


async def _mock_db_ready(_: object) -> tuple[bool, bool]:
    return False, True


async def _mock_fetch_mission(_: object, mission_id: str) -> MissionRecord:
    return MissionRecord(
        mission_id=mission_id,
        prompt="contract-test-prompt",
        requested_target_language="python",
        metadata={},
        state=MissionState.queued,
        created_at="2026-04-12T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_envelope(body: dict[str, Any]) -> bool:
    """Return True when *body* conforms to the Phase 5 error envelope schema."""
    return (
        isinstance(body.get("error"), str)
        and body.get("error") != ""
        and "detail" in body
        and isinstance(body.get("correlation_id"), str)
    )


# ---------------------------------------------------------------------------
# Error envelope shape: 4xx responses
# ---------------------------------------------------------------------------

class TestErrorEnvelopeShape:
    """Every 4xx response from the orchestrator must include error + correlation_id."""

    def test_404_mission_not_found_has_envelope(self, monkeypatch) -> None:
        from fastapi import HTTPException as _HTTPException

        async def _raise_404(_app, _mission_id):
            raise _HTTPException(status_code=404, detail="mission not found")

        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
        monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _raise_404)

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.get("/internal/missions/no-such-mission")
        assert response.status_code == 404
        body = response.json()
        assert _is_envelope(body), f"Missing envelope fields: {body}"
        assert body["error"] == "not_found"
        assert "not found" in body["detail"].lower()

    def test_400_short_fingerprint_has_envelope(self, monkeypatch) -> None:
        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.post(
            "/internal/review-approvals",
            json={
                "scope": "builder",
                "fingerprint": "short",  # < 12 chars — should fail
                "summary": "valid summary text",
            },
        )
        assert response.status_code in (400, 422)
        body = response.json()
        assert _is_envelope(body), f"Missing envelope fields: {body}"
        assert body["error"] in ("bad_request", "validation_error")

    def test_422_missing_required_field_has_envelope(self, monkeypatch) -> None:
        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.post(
            "/internal/review-approvals",
            json={
                "scope": "builder",
                # fingerprint and summary are missing
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert _is_envelope(body), f"Missing envelope fields: {body}"
        assert body["error"] == "validation_error"
        assert isinstance(body["detail"], list), "Validation errors must be a list"

    def test_410_expired_approval_has_envelope(self, monkeypatch) -> None:
        """Expired approval must return 410 Gone with the standard envelope."""
        expired_record = {
            "approval_id": "builder-approval-abcdefghijklmnop",
            "scope": "builder",
            "fingerprint": "abcdefghijklmnopqrstuvwx",
            "summary": "approved for contract test",
            "metadata": {},
            "receipt_digest": "a" * 64,
            "storage_backend": "postgres",
            "approved_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "updated_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        }

        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
        monkeypatch.setattr(
            orchestrator_main.storage,
            "get_review_approval",
            lambda _s, _id: expired_record,
        )
        # Force TTL to 1 second so the 2-day-old record is expired
        original_settings = orch_app.state.settings
        monkeypatch.setattr(
            orch_app.state,
            "settings",
            Settings(**{**original_settings.__dict__, "approval_ttl_seconds": 1}),
        )

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.get("/internal/review-approvals/builder-approval-abcdefghijklmnop")
        assert response.status_code == 410
        body = response.json()
        assert _is_envelope(body), f"Missing envelope fields: {body}"
        assert body["error"] == "gone"
        assert "expired" in body["detail"].lower()


# ---------------------------------------------------------------------------
# Review approval CRUD contract
# ---------------------------------------------------------------------------

class TestReviewApprovalContract:
    """Validate the shape of review approval create/retrieve responses."""

    _APPROVAL_RECORD: dict[str, Any] = {
        "approval_id": "builder-approval-abc123def456gh",
        "scope": "builder",
        "fingerprint": "abc123def456ghijklmnopqrst",
        "summary": "Approved for contract test",
        "metadata": {"test": True},
        "receipt_digest": "b" * 64,
        "storage_backend": "postgres",
        "approved_at": "2026-04-12T10:00:00+00:00",
        "updated_at": "2026-04-12T10:00:00+00:00",
    }

    def test_create_approval_returns_required_fields(self, monkeypatch) -> None:
        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
        monkeypatch.setattr(
            orchestrator_main.storage,
            "upsert_review_approval",
            lambda *_a, **_kw: self._APPROVAL_RECORD,
        )

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.post(
            "/internal/review-approvals",
            json={
                "scope": "builder",
                "fingerprint": "abc123def456ghijklmnopqrst",
                "summary": "Approved for contract test",
                "metadata": {"test": True},
            },
        )
        assert response.status_code == 200
        body = response.json()
        required = {"approval_id", "scope", "fingerprint", "summary",
                    "receipt_digest", "storage_backend", "approved_at", "record_path"}
        missing = required - body.keys()
        assert not missing, f"Response missing fields: {missing}"
        assert body["scope"] in ("builder", "repo")
        assert body["record_path"].startswith("orchestrator://")

    def test_get_approval_returns_required_fields(self, monkeypatch) -> None:
        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
        monkeypatch.setattr(
            orchestrator_main.storage,
            "get_review_approval",
            lambda _s, _id: self._APPROVAL_RECORD,
        )

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.get(
            f"/internal/review-approvals/{self._APPROVAL_RECORD['approval_id']}"
        )
        assert response.status_code == 200
        body = response.json()
        required = {"approval_id", "scope", "fingerprint", "summary",
                    "receipt_digest", "storage_backend", "approved_at", "record_path"}
        missing = required - body.keys()
        assert not missing, f"Response missing fields: {missing}"

    def test_get_approval_not_found_is_404_envelope(self, monkeypatch) -> None:
        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
        monkeypatch.setattr(
            orchestrator_main.storage,
            "get_review_approval",
            lambda _s, _id: None,
        )

        client = TestClient(orch_app, raise_server_exceptions=False)
        response = client.get("/internal/review-approvals/no-such-approval")
        assert response.status_code == 404
        body = response.json()
        assert _is_envelope(body)
        assert body["error"] == "not_found"

    def test_create_approval_uses_hmac_when_secret_configured(self, monkeypatch) -> None:
        """When APPROVAL_HMAC_SECRET is set the digest must differ from plain SHA256."""
        captured: list[str] = []

        def _capture_upsert(_settings, _aid, _scope, _fp, _summary, _meta, receipt_digest, *_rest, **_kw):
            captured.append(receipt_digest)
            return self._APPROVAL_RECORD

        monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
        monkeypatch.setattr(orchestrator_main.storage, "upsert_review_approval", _capture_upsert)

        # Run once without secret
        original = orch_app.state.settings
        monkeypatch.setattr(
            orch_app.state,
            "settings",
            Settings(**{**original.__dict__, "approval_hmac_secret": ""}),
        )
        client = TestClient(orch_app, raise_server_exceptions=False)
        client.post(
            "/internal/review-approvals",
            json={"scope": "builder", "fingerprint": "abc123def456ghijklmnopqrst",
                  "summary": "test", "metadata": {}},
        )

        # Run again with a secret
        monkeypatch.setattr(
            orch_app.state,
            "settings",
            Settings(**{**original.__dict__, "approval_hmac_secret": "test-hmac-secret-32chars-minimum!"}),
        )
        client.post(
            "/internal/review-approvals",
            json={"scope": "builder", "fingerprint": "abc123def456ghijklmnopqrst",
                  "summary": "test", "metadata": {}},
        )

        assert len(captured) == 2, "Expected two upsert calls"
        digest_plain, digest_hmac = captured
        assert digest_plain != digest_hmac, (
            "HMAC digest must differ from plain SHA256 digest when secret is set"
        )
        assert len(digest_plain) == 64  # sha256 hex
        assert len(digest_hmac) == 64   # hmac-sha256 hex


# ---------------------------------------------------------------------------
# Error envelope fields are always present (parametric)
# ---------------------------------------------------------------------------

_ERROR_CASES = [
    ("not_found", 404, "not found"),
    ("gone", 410, "gone"),
    ("validation_error", 422, "validation"),
]


@pytest.mark.parametrize("expected_error,status,keyword", _ERROR_CASES)
def test_error_type_matches_status_code(expected_error: str, status: int, keyword: str) -> None:
    """The ``error`` field must match the HTTP status code for all common error types."""
    from shared_runtime.error_envelope import _error_type
    assert _error_type(status) == expected_error


def test_all_common_status_codes_have_error_type() -> None:
    """Every status code in the 4xx/5xx range used by the services must map to a type."""
    from shared_runtime.error_envelope import _error_type
    for code in (400, 401, 403, 404, 409, 410, 422, 429, 500, 503):
        result = _error_type(code)
        assert result != f"http_{code}", (
            f"Status {code} falls through to generic fallback — add explicit mapping"
        )
        assert "_" in result or result.isalpha(), (
            f"Error type {result!r} for status {code} should be snake_case"
        )
