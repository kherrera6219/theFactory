# Phase 16 - Knowledge Lake Embeddings and Auto-Refresh

**Status:** Partially implemented
**Last updated:** 2026-05-19
**Depends on:** Phase 8 FETCH, vector-store adapters, Phase 15 token/cost ledger

## Validated Entry State

Phase 8 already mirrors deterministic bootstrap language documentation into the global Knowledge Lake and mission-scoped knowledge records. Qdrant and Milvus adapters exist, but they previously generated separate deterministic hash vectors and did not expose embedding model metadata. FETCH also treated an existing global documentation record as current without checking its content hash.

Provider docs checked on 2026-05-19:

- OpenAI: `text-embedding-3-large` remains the high-capability embedding default, with `text-embedding-3-small` as the lower-cost option.
- Gemini: `gemini-embedding-001` is the current Gemini API embedding model.
- Anthropic: no first-party embeddings API is available in the current official Anthropic API surface, so Anthropic is not a Phase 16 embedding provider.

## Implemented Slice

1. Centralized embedding configuration and vector generation.
   - Added `knowledge_embeddings.py`.
   - Default provider remains `deterministic` for local/offline operation.
   - OpenAI embeddings can be enabled with `KNOWLEDGE_EMBEDDING_PROVIDER=openai`.
   - Configured model defaults to `deterministic-hash-v1`; OpenAI provider defaults to `text-embedding-3-large`.

2. Shared vector-store embedding path.
   - Qdrant and Milvus now use the same embedding helper.
   - Vector payloads include embedding provider, model, and dimensions.
   - Existing default vector size stays `64` to avoid changing local collection compatibility unless the operator opts in.

3. Refresh detection for bootstrap documentation.
   - IS-agent FETCH compares global Knowledge Lake content hashes.
   - Changed bootstrap docs are refreshed.
   - Current docs are not rewritten globally, but are still mirrored to the mission scope.
   - FETCH result now records refreshed and unchanged languages plus embedding provider/model.

4. Mission Control visibility.
   - Mission Detail Knowledge Lake panel now shows embedding model, refresh state, refreshed languages, and unchanged languages.

## Remaining Implementation Plan

1. Add provider-backed Gemini embeddings.
   - Implement `gemini-embedding-001` call path.
   - Keep deterministic fallback if credentials or provider response are unavailable.

2. Add scheduled auto-refresh.
   - Add a refresh job that can re-index all supported bootstrap docs and future external docs.
   - Record refresh history and last-success timestamps.

3. Add retrieval quality tests.
   - Add deterministic nearest-neighbor fixtures for Qdrant/Milvus vector payloads.
   - Add mission-context retrieval tests that prove FETCH context is relevant to downstream extraction/generation.

4. Add operator controls.
   - Document `KNOWLEDGE_EMBEDDING_PROVIDER`, `KNOWLEDGE_EMBEDDING_MODEL`, `KNOWLEDGE_REFRESH_ENABLED`, and vector-size settings.
   - Add Mission Control settings/readiness display for embedding provider status.

5. Connect with Phase 15.
   - Once the token/cost ledger exists, record embedding API usage and cost estimates.

## Non-Goals

- Do not require live embedding provider credentials for local operation.
- Do not silently change existing Qdrant/Milvus collection dimensions.
- Do not send sensitive source bundles to external embedding providers without future data-classification gates.
- Do not claim a complete operational knowledge lake until scheduled refresh and retrieval quality tests exist.

## Validation

- [x] Embedding config defaults to deterministic offline mode.
- [x] OpenAI embedding requests include the configured dimensions when enabled.
- [x] Missing OpenAI credentials fall back to deterministic vectors.
- [x] Qdrant and Milvus payloads include embedding metadata.
- [x] FETCH refreshes changed docs and skips unchanged global docs.
- [x] Mission Detail renders embedding provider/model and refresh status.
- [ ] Gemini embedding provider implemented.
- [ ] Scheduled refresh job implemented.
- [ ] Retrieval quality tests implemented.
- [ ] Phase 15 ledger records embedding API usage.
