import asyncio
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

orchestrator_main = importlib.import_module("orchestrator.main")
errors = importlib.import_module("shared_runtime.errors")

FactoryError = errors.FactoryError
ErrorCategory = errors.ErrorCategory
ErrorSeverity = errors.ErrorSeverity


class _FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


def _call_handler(err: "FactoryError", headers: dict[str, str] | None = None):
    request = _FakeRequest(headers)
    return asyncio.run(orchestrator_main._factory_error_handler(request, err))


def test_handler_returns_user_payload_only() -> None:
    err = FactoryError(
        category=ErrorCategory.INTEGRITY,
        code_number=1,
        component="ArtifactStore",
        operation="LoadArtifact",
        user_message="A file failed its integrity check.",
        developer_message="sha256 mismatch SECRET-DETAIL",
        recovery_action="Restore a trusted backup.",
        severity=ErrorSeverity.CRITICAL,
    )
    resp = _call_handler(err)
    body = json.loads(resp.body)

    assert resp.status_code == 500  # CRITICAL → 500
    detail = body["detail"]
    assert detail["user_message"] == "A file failed its integrity check."
    assert detail["recovery_action"] == "Restore a trusted backup."
    assert detail["error_code"] == "FACTORY-INTEGRITY-001"
    # developer_message must never reach the client payload.
    assert "developer_message" not in detail
    assert "SECRET-DETAIL" not in resp.body.decode()


def test_handler_severity_status_mapping() -> None:
    def _status(sev: "ErrorSeverity") -> int:
        err = FactoryError(
            category=ErrorCategory.VALIDATION,
            code_number=1,
            component="C",
            operation="O",
            user_message="bad",
            severity=sev,
        )
        return _call_handler(err).status_code

    assert _status(ErrorSeverity.RECOVERABLE) == 400
    assert _status(ErrorSeverity.WARNING) == 400
    assert _status(ErrorSeverity.CRITICAL) == 500
    assert _status(ErrorSeverity.FATAL) == 500
    assert _status(ErrorSeverity.INFO) == 200


def test_handler_populates_correlation_id_from_header() -> None:
    err = FactoryError(
        category=ErrorCategory.STORAGE,
        code_number=1,
        component="C",
        operation="O",
        user_message="x",
    )
    assert err.correlation_id is None
    _call_handler(err, headers={"x-request-id": "corr-xyz"})
    assert err.correlation_id == "corr-xyz"
