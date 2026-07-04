# LLM Safety Filter and Document Parser

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers, Security

This document was rewritten on 2026-07-03 — the previous version described an `LLMSafetyFilter` class, a `LocalOnlyViolation` exception, and a `local_only` routing concept that don't exist, while omitting the real `shared_runtime/prompt_guard.py` and `shared_runtime/pii_guard.py` modules it was supposed to document. The document-parser section also described `ParsedDocument`/`DocumentBlock` dataclasses and YAML/TOML support that aren't implemented.

## LLM Safety — Two Layers

There are actually **two** separate safety-check layers in this codebase, not one:

### 1. `services/orchestrator/orchestrator/llm_safety.py` — pattern-based outbound/inbound scan

Pure, synchronous functions with no I/O:

```python
def check_outbound_prompt(prompt: str, call_context: str) -> list[str]: ...  # empty list = safe
def check_inbound_response(text: str, call_context: str) -> list[str]: ...
def sanitize_outbound_prompt(prompt: str) -> str: ...  # redacts matches to "[REDACTED]"
```

- `check_outbound_prompt()` scans for secret/PII-shaped patterns before a prompt reaches any provider (API key prefixes like `sk-`/`ghp_`/`github_pat_`, SSN format, Visa/Mastercard card-number format).
- `check_inbound_response()` scans model *output* for injection/jailbreak indicators (`IGNORE ALL PREVIOUS INSTRUCTIONS`, `You are now DAN`, `<|im_start|> system`, etc.).
- `sanitize_outbound_prompt()` is the log-only-mode counterpart: instead of blocking, it redacts matches to `[REDACTED]` before sending. Which behavior is used is controlled by `LLM_SAFETY_BLOCK_ENABLED` (see `SETTINGS_REFERENCE.md`, default `false`).
- No `LLMSafetyFilter` class, no `local_only` concept, no `LocalOnlyViolation` exception exist anywhere in this module or elsewhere in the codebase.

### 2. `shared_runtime/prompt_guard.py` and `shared_runtime/pii_guard.py` — the shared-library layer

These are imported by every backend service (orchestrator, api-gateway, pod-worker), not just the LLM delegation path:
- `prompt_guard.py` provides prompt-injection risk detection (`check_prompt`/`check_user_input`-style functions) with a risk-level scale and a configurable block threshold (`PROMPT_GUARD_BLOCK_ENABLED`/`PROMPT_GUARD_BLOCK_LEVEL` in `llm_delegation/config.py`, default enabled at `high`).
- `pii_guard.py` provides `detect_pii`/`redact_pii`/`scan_dict_for_pii` — a flat, non-tiered regex scanner for SSNs, credit cards, emails, phone numbers, JWTs, generic API-key-shaped strings, and password/token key-value pairs. It is not conditioned on a mission's `DataClassification` tier (see `DATA_CLASSIFICATION_POLICY.md` for that correction).

Both are regex/heuristic-based, not ML-based classifiers — they are a real but bypassable defense-in-depth layer (a sufficiently obfuscated secret or crafted injection string can evade pattern matching), which is an accepted, documented limitation, not a bug.

## Document Parser — `services/orchestrator/orchestrator/document_parser.py`

One function, not a dataclass-based API:

```python
def parse_document(content: bytes, content_type: str, filename: str) -> str | None: ...
```

- Routes by `content_type` first, falling back to filename extension (since many clients send `application/octet-stream` regardless of actual file type).
- Supports PDF (`pypdf`), Word `.docx` (`python-docx`), PowerPoint `.pptx` (`python-pptx`), and plain Markdown/text (`.md`/`.txt`, decoded as UTF-8 with `errors="replace"`). **No YAML or TOML support exists.**
- Every extraction path truncates to `MAX_EXTRACTED_CHARS = 50_000` characters — silently, not via an exception — so a single large attachment can't blow the LLM context window or the knowledge-lake payload.
- All parsing is wrapped in a broad `try/except Exception`, returning `None` and logging a warning on any failure (corrupt file, missing optional dependency, encrypted document) — mission intake must proceed regardless of a single attachment's parse failure. There is no `ParsedDocument`/`DocumentBlock` dataclass; callers get either a plain string or `None`.

## Related Docs

- `SETTINGS_REFERENCE.md` — `LLM_SAFETY_BLOCK_ENABLED`, `PROMPT_GUARD_BLOCK_ENABLED`/`_LEVEL`
- `LLM_DELEGATION.md` — where `check_user_input()` (backed by `prompt_guard.py`) is called before every outbound provider call
- `DATA_CLASSIFICATION_POLICY.md` — the real (thin) tier enforcement, which `pii_guard.py` does not participate in
