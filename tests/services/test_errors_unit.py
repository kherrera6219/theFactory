import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

errors = importlib.import_module("shared_runtime.errors")
FactoryError = errors.FactoryError
ErrorCategory = errors.ErrorCategory
ErrorSeverity = errors.ErrorSeverity


def test_make_error_code_format() -> None:
    assert errors.make_error_code(ErrorCategory.STORAGE, 1) == "FACTORY-STORAGE-001"
    assert errors.make_error_code(ErrorCategory.INTEGRITY, 42) == "FACTORY-INTEGRITY-042"
    assert errors.make_error_code(ErrorCategory.IMPORT_EXPORT, 7) == "FACTORY-IMPORT_EXPORT-007"


def _make(**overrides) -> "FactoryError":
    base = dict(
        category=ErrorCategory.STORAGE,
        component="WorkspaceService",
        operation="OpenWorkspace",
        user_message="The workspace could not be opened.",
        developer_message="file locked",
        recovery_action="Close other apps and retry.",
        severity=ErrorSeverity.RECOVERABLE,
        code_number=1,
    )
    base.update(overrides)
    return FactoryError(**base)


def test_factory_error_is_raisable() -> None:
    try:
        raise _make()
    except FactoryError as exc:
        assert isinstance(exc, Exception)
        assert exc.error_code == "FACTORY-STORAGE-001"
        # Exception str carries the sanitised developer message.
        assert str(exc) == "file locked"


def test_to_dict_has_standard_shape() -> None:
    err = _make()
    d = err.to_dict()
    for key in (
        "error_id", "error_code", "severity", "category", "component",
        "operation", "user_message", "developer_message", "recovery_action",
        "timestamp", "correlation_id",
    ):
        assert key in d
    assert d["error_code"] == "FACTORY-STORAGE-001"
    assert d["severity"] == "RecoverableError"
    assert d["category"] == "StorageError"


def test_user_payload_is_secret_free() -> None:
    err = _make(developer_message="secret token abc123 in here")
    payload = err.to_user_payload()
    assert set(payload.keys()) == {"user_message", "recovery_action", "error_code"}
    # developer_message / component / operation must NOT leak to the user payload.
    assert "developer_message" not in payload
    assert "abc123" not in " ".join(payload.values())


def test_developer_message_is_sanitized_at_construction() -> None:
    err = _make(
        developer_message="password=supersecret contact admin@example.com",
    )

    assert "supersecret" not in err.developer_message
    assert "admin@example.com" not in err.developer_message
    assert "[REDACTED-CREDENTIAL]" in err.developer_message
    assert "[REDACTED-EMAIL]" in err.developer_message
    assert str(err) == err.developer_message


def test_format_user_message_four_lines() -> None:
    err = _make()
    text = err.format_user_message()
    lines = text.split("\n")
    assert lines[0] == "Something went wrong."
    assert lines[1].startswith("What happened: ")
    assert lines[2].startswith("What you can do: ")
    assert lines[3] == "Error code: FACTORY-STORAGE-001"


def test_unique_error_ids() -> None:
    a = _make()
    b = _make()
    assert a.error_id != b.error_id


def test_wrap_unexpected() -> None:
    original = ValueError("bad value")
    wrapped = errors.wrap_unexpected(
        original, component="X", operation="Y", correlation_id="corr-1"
    )
    assert wrapped.category is ErrorCategory.UNEXPECTED
    assert wrapped.error_code == "FACTORY-UNEXPECTED-001"
    assert wrapped.severity is ErrorSeverity.CRITICAL
    assert wrapped.correlation_id == "corr-1"
    assert "ValueError: bad value" == wrapped.developer_message


def test_wrap_unexpected_sanitizes_exception_text() -> None:
    original = ValueError("token=short-secret for owner@example.com")

    wrapped = errors.wrap_unexpected(original, component="X", operation="Y")

    assert "short-secret" not in wrapped.developer_message
    assert "owner@example.com" not in wrapped.developer_message
    assert "[REDACTED-CREDENTIAL]" in wrapped.developer_message


def test_correlation_id_default_none() -> None:
    assert _make().correlation_id is None
