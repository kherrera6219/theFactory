# LLM Safety Filter and Document Parser

Last updated: 2026-06-27

Document version: 2026.06.11  
Status: Canonical  
Audience: Developers and security reviewers

---

## LLM Safety Filter

### Overview

`llm_safety.py` (3 KB, `services/orchestrator/orchestrator/llm_safety.py`) implements a lightweight pre-dispatch safety filter that inspects every prompt before it is sent to an external LLM provider. It is the last checkpoint in the prompt pipeline and sits between `prompt_registry.py` and the `llm_delegation/` router.

The filter has two responsibilities:
1. **Redaction** — scrub any content classified as `SENSITIVE` or `SECRET` by `DATA_CLASSIFICATION_POLICY.md` before the prompt leaves the system boundary.
2. **Block** — hard-block prompt dispatch for any mission marked `local_only` in its agent persona when the target provider is external.

### Code Location

```
services/orchestrator/orchestrator/llm_safety.py   # 3 KB
```

**Related files:**

| File | Relationship |
|---|---|
| `prompt_registry.py` | Calls `LLMSafetyFilter.check()` before returning a prompt to the caller |
| `llm_delegation/` | Receives the post-filter prompt from the delegation router |
| `DATA_CLASSIFICATION_POLICY.md` | Defines classification tags the filter enforces |
| `SENSITIVE_CODE_HANDLING_POLICY.md` | Defines `local_only` persona tag and routing rules |

### Filter Pipeline

```
prompt_registry.get(key, context)
        │
        ▼
LLMSafetyFilter.check(prompt, mission_context)
        │
        ├── classify(mission_context)      ← DATA_CLASSIFICATION_POLICY tags
        │       if SENSITIVE or SECRET:
        │           redact(prompt)         ← replaces classified tokens with [REDACTED]
        │
        ├── check_local_only(persona)      ← SENSITIVE_CODE_HANDLING_POLICY
        │       if local_only AND provider != "ollama":
        │           raise LocalOnlyViolation
        │
        └── return sanitised_prompt
```

### `LocalOnlyViolation`

When a `local_only` mission attempts to dispatch to an external provider, `LLMSafetyFilter` raises `LocalOnlyViolation`. This exception is caught by `llm_delegation/router.py`, which logs a `SAFETY_BLOCK` audit event and returns an error to the caller. The mission is routed to `HUMAN_REVIEW` state.

### Redaction Rules

Redaction patterns are loaded from `DATA_CLASSIFICATION_POLICY.md` at startup. The filter uses regex-based token matching. Common redaction targets:

- API keys and tokens (pattern: `[A-Za-z0-9_\-]{32,}` in certain contexts)
- File paths containing classified directory prefixes
- Database connection strings
- Content explicitly tagged `SECRET` in the mission metadata

Redacted prompts are stored in the audit log with a `PROMPT_REDACTED` event — the original prompt is never logged externally.

### Operational Notes

- Redaction is logged but not alerted by default. Set `SAFETY_ALERT_ON_REDACT=true` to fire a Prometheus alert when redaction occurs.
- `LocalOnlyViolation` fires a `CRITICAL` alert immediately.
- The filter can be bypassed in test mode via `LLM_SAFETY_BYPASS=true` (never set in production).

---

## Document Parser

### Overview

`document_parser.py` (3 KB, `services/orchestrator/orchestrator/document_parser.py`) is a lightweight utility that parses structured documents (Markdown, YAML, JSON, TOML, plain text) supplied as mission inputs into a normalised `ParsedDocument` representation for ingestion into the Knowledge Lake.

### Code Location

```
services/orchestrator/orchestrator/document_parser.py   # 3 KB
```

### Supported Formats

| Format | Parser used | Notes |
|---|---|---|
| Markdown (`.md`) | Custom sectioning parser | Splits by heading levels into labelled blocks |
| YAML (`.yaml`, `.yml`) | `PyYAML` | Loaded as dict, each top-level key becomes a block |
| JSON (`.json`) | stdlib `json` | Each top-level key becomes a block |
| TOML (`.toml`) | `tomllib` (Python 3.11 stdlib) | Each section becomes a block |
| Plain text (`.txt`, other) | Line-window chunker | 50-line windows with 10-line overlap |

### `ParsedDocument` Dataclass

```python
@dataclass
class ParsedDocument:
    source_path: str
    format: str                     # "markdown" | "yaml" | "json" | "toml" | "text"
    blocks: list[DocumentBlock]     # ordered list of content blocks
    metadata: dict                  # frontmatter or top-level keys
    char_count: int
    mission_id: str

@dataclass
class DocumentBlock:
    block_id: str
    label: str                      # heading text or key name
    content: str
    level: int | None               # heading level for Markdown; None for others
```

### Usage

The Document Parser is called by the Knowledge Lake's `write` path when a `DOCUMENT`-type `KnowledgeNode` is received. The parser runs first, then `KnowledgeEmbeddings` chunks and embeds each `DocumentBlock` separately, preserving label metadata as vector payload.

### Operational Notes

- Files larger than `DOCUMENT_PARSER_MAX_BYTES` (default: 5 MB) are rejected with a `DocumentTooLarge` error. Adjust via `settings.py`.
- Binary files and non-UTF-8 content are rejected at ingestion time with a `DocumentParseError`.
