"""Local-First standard error model (shared across services).

Implements the **Local-First Error Handling Standard** (§2 categories, §3 severities,
§6 standard error object, §7 error-code naming) so every service raises and serialises
errors the same way.

Design goals:

- One ``FactoryError`` type that is **both** a raisable ``Exception`` and a carrier of the
  full standard object (so it flows through normal Python control flow and serialises at the
  boundary).
- A strict separation between the **user-facing** message (``user_message`` +
  ``recovery_action`` + ``error_code``, formatted per §4) and the **developer-facing** detail
  (``developer_message`` — a *sanitised* exception summary that never contains secrets).
- Stable, searchable error codes of the form ``FACTORY-<CATEGORY>-<NNN>`` (§7).

Stdlib-only — no new dependency.

Example::

    raise FactoryError(
        category=ErrorCategory.STORAGE,
        code_number=1,
        component="WorkspaceService",
        operation="OpenWorkspace",
        user_message="The workspace could not be opened.",
        developer_message="workspace file was locked or unavailable",
        recovery_action="Close other applications using the file and try again.",
        severity=ErrorSeverity.RECOVERABLE,
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from shared_runtime.pii_guard import redact_pii

# Application prefix for this codebase (Error Handling Standard §7).
APP_PREFIX = "FACTORY"


class ErrorCategory(str, Enum):
    """The 13 error categories defined by the standard (§2)."""

    VALIDATION = "ValidationError"
    CONFIGURATION = "ConfigurationError"
    STORAGE = "StorageError"
    ENCRYPTION = "EncryptionError"
    INTEGRITY = "IntegrityError"
    SIGNATURE = "SignatureError"
    PERMISSION = "PermissionError"
    FILESYSTEM = "FileSystemError"
    DATABASE = "DatabaseError"
    MODEL_EXECUTION = "ModelExecutionError"
    GENERATION = "GenerationError"
    IMPORT_EXPORT = "ImportExportError"
    PLUGIN_EXECUTION = "PluginExecutionError"
    UNEXPECTED = "UnexpectedError"

    @property
    def code_token(self) -> str:
        """Short UPPER-SNAKE token used inside an error code (e.g. ``STORAGE``)."""
        return self.name


class ErrorSeverity(str, Enum):
    """The 5 severity levels defined by the standard (§3)."""

    INFO = "Info"
    WARNING = "Warning"
    RECOVERABLE = "RecoverableError"
    CRITICAL = "CriticalError"
    FATAL = "FatalError"


def make_error_code(category: ErrorCategory, number: int) -> str:
    """Build a stable error code ``FACTORY-<CATEGORY>-<NNN>`` (§7).

    The number is zero-padded to 3 digits for sortable, searchable codes.
    """
    return f"{APP_PREFIX}-{category.code_token}-{number:03d}"


@dataclass
class FactoryError(Exception):
    """Standard error object (§6) that is also a raisable exception.

    The ``developer_message`` is sanitised during construction so serialized errors,
    tracebacks, and logs cannot expose recognized PII or credentials.
    """

    category: ErrorCategory
    component: str
    operation: str
    user_message: str
    developer_message: str = ""
    recovery_action: str = "Try again."
    severity: ErrorSeverity = ErrorSeverity.RECOVERABLE
    code_number: int = 1
    error_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        self.developer_message, _ = redact_pii(self.developer_message)
        # Initialise the Exception side with the sanitised developer message so tracebacks
        # and ``str(exc)`` carry useful, secret-free context.
        super().__init__(self.developer_message or self.user_message)

    @property
    def error_code(self) -> str:
        """The stable ``FACTORY-<CATEGORY>-<NNN>`` code for this error."""
        return make_error_code(self.category, self.code_number)

    def to_dict(self) -> dict[str, object]:
        """Serialise to the standard error object (§6) for logs/APIs."""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "severity": self.severity.value,
            "category": self.category.value,
            "component": self.component,
            "operation": self.operation,
            "user_message": self.user_message,
            "developer_message": self.developer_message,
            "recovery_action": self.recovery_action,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }

    def to_user_payload(self) -> dict[str, str]:
        """The minimal, secret-free payload safe to send to a UI client.

        Excludes ``developer_message``, ``component``, ``operation`` — anything that could
        leak internals. The UI renders this with :func:`format_user_message`.
        """
        return {
            "user_message": self.user_message,
            "recovery_action": self.recovery_action,
            "error_code": self.error_code,
        }

    def format_user_message(self) -> str:
        """Render the four-line user-facing format from the standard (§4)."""
        return (
            "Something went wrong.\n"
            f"What happened: {self.user_message}\n"
            f"What you can do: {self.recovery_action}\n"
            f"Error code: {self.error_code}"
        )


def wrap_unexpected(
    exc: BaseException,
    *,
    component: str,
    operation: str,
    correlation_id: str | None = None,
) -> FactoryError:
    """Wrap an arbitrary exception as an ``UnexpectedError`` FactoryError.

    The ``developer_message`` is the exception type name + ``str(exc)`` and is sanitised by
    ``FactoryError`` during construction. Use at application boundaries to guarantee every
    escaping error has a stable code and secret-free developer detail.
    """
    return FactoryError(
        category=ErrorCategory.UNEXPECTED,
        component=component,
        operation=operation,
        user_message="An unexpected error occurred.",
        developer_message=f"{type(exc).__name__}: {exc}",
        recovery_action="Try again. If the problem persists, generate diagnostics.",
        severity=ErrorSeverity.CRITICAL,
        code_number=1,
        correlation_id=correlation_id,
    )
