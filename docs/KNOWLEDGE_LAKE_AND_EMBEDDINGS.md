# Knowledge Lake and Embeddings

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers and operators

## Overview

The **Knowledge Lake** is a PostgreSQL-backed shared documentation store that the IS Agent
(AGENT-06-IS) populates during the FETCH phase of Mission Flow v2.  Language specialists read from
it during the BUILD phase to get library/API context injected into their prompts.

**Key design decisions:**

- PostgreSQL (`mission_knowledge` table) is the **single source of truth** — all reads and writes go
  there first.
- Qdrant is an **optional semantic mirror** — when a real embedding provider is configured, indexed
  chunks are also written to Qdrant so vector similarity search can be layered on top.  Qdrant
  failures never fail the PostgreSQL write.
- When no real embedding provider is configured (the compose default), the system falls back to
  PostgreSQL keyword overlap search.  No stale hash vectors are written to Qdrant.

## Code Locations

| File | Role |
|------|------|
| `services/orchestrator/orchestrator/knowledge_lake.py` | Public API — module-level functions, not a class |
| `services/orchestrator/orchestrator/knowledge_embeddings.py` | Vector generation — Gemini, OpenAI, and deterministic (SHA-256) providers |
| `services/orchestrator/orchestrator/storage_logicnodes.py` | Storage layer — `upsert_knowledge`, `list_knowledge` against `mission_knowledge` table |
| `services/orchestrator/orchestrator/qdrant_store.py` | Qdrant helpers — `ensure_collection`, `upsert_knowledge`, `_request_json` |

## Architecture

```
  is_agent.py bootstrap seeding (_upsert_knowledge_safe)
          │
          │  storage.upsert_knowledge(...) directly — NOT via
          │  knowledge_lake.index_documentation(), which is defined but
          │  never called anywhere in the codebase as of 2026-07-03
          ▼
  storage_logicnodes.py
     └── upsert_knowledge()        → PostgreSQL mission_knowledge (always)

  knowledge_lake.py's own index_documentation() (unused today, kept as the
  intended entry point for future callers) would additionally do:
     └── _mirror_to_qdrant()       → Qdrant (only when real embedding + Qdrant enabled)

  Language Specialists — BUILD phase
          │
          │  get_language_context(language)
          ▼
  knowledge_lake.py
     └── list_knowledge()          → PostgreSQL (always)

  query_documentation(language, concept)  [used by codegen agents]
     ├── _semantic_search_enabled()?
     │     yes → _vector_search()  → Qdrant similarity search
     │     no  → skip
     └── _keyword_search()         → PostgreSQL keyword overlap (fallback / only path)
```

## Public API

All entry points are module-level functions in `knowledge_lake.py`. There is no class.

### `is_stocked(*, settings, mission_id=None, language=None) → bool`

Returns True if the Knowledge Lake has entries for the given scope.  Reads PostgreSQL.

- Pass `language` to check whether the global bootstrap doc for that language is indexed.
- Pass `mission_id` (without language) to check whether a mission has any knowledge rows.

### `index_documentation(*, settings, language, library, content) → bool`

Upserts a documentation chunk.  PostgreSQL is always written; Qdrant is written only when
`_semantic_search_enabled()` returns True (real provider configured, Qdrant enabled, and a
non-empty API key available).

Returns True when the PostgreSQL write succeeds.

### `query_documentation(*, settings, language, concept, top_k=5) → list[dict]`

Retrieves the most relevant knowledge records for a language and concept.

1. If semantic search is enabled, tries Qdrant vector search first (using `RETRIEVAL_QUERY` task
   type and the concept as natural-language query text).
2. Falls back to PostgreSQL keyword overlap scoring if Qdrant returns nothing or is unavailable.

Each result: `{"knowledge_id": str, "content": dict, "score": float}`

### `get_language_context(*, settings, language) → str | None`

Returns the bootstrap documentation text for a language as a single string (truncated to 8 000
characters).  Used by codegen specialists to inject library context into their system prompts.
Returns None when nothing is indexed or storage is unavailable.

### `embed_text(text, settings) → list[float] | None`

Async helper that returns a real embedding vector for arbitrary text, or None when no real provider
is configured.  Runs the provider call in a thread via `asyncio.to_thread` so the event loop is
never blocked.

### `broadcast_knowledge_ready(*, settings, languages, mission_id) → bool`

Publishes a `knowledge_ready` event to the Protocol Bus (Sigma lane) so subscribers know that
bootstrap documentation has been indexed for the listed languages.  Fire-and-forget — the mission
proceeds regardless of the result.

## Embedding Pipeline

`knowledge_embeddings.py` provides three provider paths:

| Provider | Env var | Model | Notes |
|----------|---------|-------|-------|
| `gemini` | `GEMINI_API_KEY` or `KNOWLEDGE_EMBEDDING_API_KEY` | `gemini-embedding-001` | Uses Gemini embedContent API; supports `task_type` (RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY) |
| `openai` | `OPENAI_API_KEY` or `KNOWLEDGE_EMBEDDING_API_KEY` | `text-embedding-3-large` | Uses OpenAI /v1/embeddings; `dimensions` parameter passed directly |
| `deterministic` | — | SHA-256 hash | No API call; produces vectors that are stable but semantically meaningless (not suitable for similarity search) |

`KNOWLEDGE_EMBEDDING_API_KEY` is checked first; if empty, the matching global provider key is used.

### Fallback chain

```
vector_for_content(content, task_type="RETRIEVAL_DOCUMENT")
  ├── provider == "openai"  → _openai_embedding()  → returns vector or None
  ├── provider == "gemini"  → _gemini_embedding(task_type=task_type)  → returns vector or None
  └── either returns None   → _deterministic_vector()  (SHA-256, always succeeds)
```

The deterministic fallback guarantees `vector_for_content` never raises — but its output is
useless for similarity search and is only written to Qdrant when `_semantic_search_enabled()`
has already confirmed a real key is available (so in practice the fallback path is only exercised
when indexing, not in Qdrant).

## Semantic Search Gate

`_semantic_search_enabled(settings)` returns True **only** when all three conditions hold:

1. `QDRANT_ENABLED=true` and a Qdrant URL is reachable
2. `KNOWLEDGE_EMBEDDING_PROVIDER` is `gemini` or `openai`
3. A non-empty API key exists (`KNOWLEDGE_EMBEDDING_API_KEY`, or `GEMINI_API_KEY` / `OPENAI_API_KEY` matching the provider)

If condition 3 fails, semantic search is silently disabled and the system uses PostgreSQL keyword
search only — no hash vectors are written to Qdrant.

## Configuration

| Env var | Default (compose) | Description |
|---------|-------------------|-------------|
| `KNOWLEDGE_EMBEDDING_PROVIDER` | `deterministic` | `gemini`, `openai`, or `deterministic` |
| `KNOWLEDGE_EMBEDDING_API_KEY` | *(empty)* | Dedicated embedding key; overrides global provider key |
| `KNOWLEDGE_EMBEDDING_MODEL` | *(empty → per-provider default)* | Override embedding model name |
| `KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS` | `10.0` | HTTP timeout for embedding API calls |
| `QDRANT_ENABLED` | `true` | Enable Qdrant mirror (semantic search requires this AND a real provider) |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant endpoint |
| `QDRANT_VECTOR_SIZE` | `256` | Embedding dimensions (minimum recommended: 256) |
| `QDRANT_COLLECTION` | `mission_knowledge` | Qdrant collection name |
| `KNOWLEDGE_REFRESH_ENABLED` | `true` | Allow IS Agent to re-index on refresh cycles |
| `KNOWLEDGE_REFRESH_INTERVAL_SECONDS` | `3600` | How often the IS Agent refreshes bootstrap docs |

> **Compose default is `deterministic`**: Out-of-the-box `make up` uses SHA-256 hash vectors.
> To enable real semantic search, set `KNOWLEDGE_EMBEDDING_PROVIDER=gemini` (or `openai`) and
> supply a matching API key in your `.env`, then restart the orchestrator.

## Global Scope Bootstrap

On startup, `ensure_db_schema()` creates a synthetic `MissionRecord` with
`mission_id="__knowledge_lake__"` in state `COMPLETE`.  All global language bootstrap docs (e.g.
`docs.python.bootstrap`, `docs.javascript.bootstrap`) are parented under this sentinel mission to
satisfy the foreign-key constraint on `mission_knowledge` without needing a real mission context.

## Known Limitations

- **No chunking**: Each `index_documentation` call writes the entire library content as one chunk.
  Large docs are stored whole; retrieval precision degrades for very long content.
- **No re-ranking**: `query_documentation` returns Qdrant cosine scores or keyword overlap scores
  directly — no AIM-context re-ranking exists.
- **No mission-scoped knowledge**: All bootstrap docs are written to the global
  `__knowledge_lake__` scope.  Per-mission knowledge isolation is not currently implemented.
- **Milvus and Neo4j are not used here**: They are separate feature-flagged subsystems and are not
  part of the Knowledge Lake pipeline.
