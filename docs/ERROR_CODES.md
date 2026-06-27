# theFactory — Error Code Registry

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

**Standard:** Local-First Error Handling Standard §7 — `FACTORY-<CATEGORY>-<NNN>`.
**Source of truth for categories/severities:** `shared_runtime/errors.py`
(`ErrorCategory`, `ErrorSeverity`, `make_error_code`).

Codes are stable and searchable. When you add a new code, append it here and use the next
free number within its category. Never renumber an existing code.

## Severity levels (§3)
`Info` · `Warning` · `RecoverableError` · `CriticalError` · `FatalError`

## Categories (§2) and allocated codes

| Code | Severity | When raised | User message / recovery |
|---|---|---|---|
| `FACTORY-UNEXPECTED-001` | Critical | Catch-all wrap at an application boundary (`wrap_unexpected`) | "An unexpected error occurred." / Try again; generate diagnostics |
| `FACTORY-VALIDATION-001` | Recoverable | Request/payload fails validation | "The request was not valid." / Correct the input and retry |
| `FACTORY-STORAGE-001` | Recoverable | Object/blob store read/write failure | "Storage is temporarily unavailable." / Try again shortly |
| `FACTORY-DATABASE-001` | Critical | DB transaction failed / rolled back | "A data operation could not be completed." / Try again |
| `FACTORY-INTEGRITY-001` | Critical | SHA-256 digest mismatch on load/import | "A file failed its integrity check." / Restore a trusted backup |
| `FACTORY-SIGNATURE-001` | Critical | ECDSA signature missing/invalid on import | "A file's signature could not be verified." / Import a verified copy |
| `FACTORY-ENCRYPTION-001` | Critical | Decryption failed for current identity | "This data could not be decrypted." / Use the account that created it |
| `FACTORY-GENERATION-001` | Recoverable | Empty/malformed generated output | "Generation did not produce a valid result." / Retry the mission |
| `FACTORY-PLUGIN_EXECUTION-001` | Recoverable | Sandboxed code execution failed/timed out | "A generated step could not run." / Retry or adjust the request |
| `FACTORY-IMPORT_EXPORT-001` | Recoverable | Import/export validation failed | "The file could not be imported/exported." / Check the file and retry |
| `FACTORY-PERMISSION-001` | Recoverable | Operation not permitted for caller | "You do not have permission for this action." / Check access and retry |
| `FACTORY-FILESYSTEM-001` | Recoverable | Atomic write / file op failed | "A file could not be saved." / Free up space or retry |
| `FACTORY-CONFIGURATION-001` | Critical | Required configuration missing/invalid | "The application is not configured correctly." / Check settings |
| `FACTORY-MODEL_EXECUTION-001` | Recoverable | LLM/model call failed | "An AI step could not complete." / Retry the mission |

> Numbers are allocated per category. The `001` rows above are the seed allocations; add
> `002`, `003`, … within a category as new distinct conditions are introduced.

## Usage

```python
from shared_runtime.errors import FactoryError, ErrorCategory, ErrorSeverity

raise FactoryError(
    category=ErrorCategory.INTEGRITY,
    code_number=1,                      # → FACTORY-INTEGRITY-001
    component="ArtifactStore",
    operation="LoadArtifact",
    user_message="A file failed its integrity check.",
    developer_message="sha256 mismatch: expected … got …",   # sanitised, no secrets
    recovery_action="Restore a trusted backup or import a verified copy.",
    severity=ErrorSeverity.CRITICAL,
)
```

At an API/UI boundary, send `err.to_user_payload()` (secret-free) and log `err.to_dict()`.
