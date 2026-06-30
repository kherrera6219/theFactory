# Semantic Bus Plan (Stage 4 — STUB)

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Stub — not scheduled
Audience: Maintainers and AI coding agents

> **This is a stub.** It records the intent, prerequisites, and the single
> reserved hook that already exists in the schema, so the full Protocol Bus
> program is documented. It is **not scheduled**, is the most speculative stage,
> and must not be started before Stages 1–3 land. See
> `PROTOCOL_BUS_PROGRAM_ROADMAP.md` for context.

---

## Purpose

Move the bus from **lexical** routing to **semantic** routing. Today every
message is routed by a literal channel string — `protocol:{lane}:{recipient}`
or `protocol:{lane}:broadcast` (`_resolve_channels` in
`protocol-bus-mcp/protocol_bus/mcp_server.py`). The semantic-bus goal is to
dispatch (or fan out) messages by **embedding similarity** to interested
consumers' declared interests, so a producer can address "whoever is relevant to
this knowledge/intent" rather than naming a recipient.

## The hook that already exists

`SigmaPayload.embedding_ref` is present in the schema today but explicitly
reserved:

- `mcp_server.py`: `embedding_ref` is "reserved for future semantic routing —
  not computed, stored, or matched today."
- `knowledge_lake.py`: the IS-Agent broadcast sets `embedding_ref` to a constant
  knowledge-lake id; it is carried, not matched.

Stage 4 is what finally *uses* that field (and likely generalizes it beyond
Sigma).

## Hard prerequisites

1. **Stages 2 and 3 complete.** Semantic routing replaces the routing layer; the
   bus must already own control flow (EDCP) and be exercised by independent
   identity-bearing consumers (Agent Runtime Split) before similarity dispatch is
   meaningful or safe.
2. **Production-real embedding path.** The knowledge-lake embedding pipeline
   (S1-01 / Qdrant — `knowledge_embeddings.py`, `qdrant_store.py`) must be
   producing real query/document embeddings, not placeholders. Semantic routing
   is only as good as the embeddings behind it.
3. **A consumer-interest model.** There is no concept today of a consumer
   declaring "what I'm interested in" as an embedding. That registry/model is net
   new and is the core design problem of this stage.

## Candidate phases (high level — to be refined)

- **4a — Compute and store `embedding_ref` for real.** Populate it from the
  knowledge-lake embedding path so messages carry a resolvable semantic vector
  reference instead of a constant.
- **4b — Consumer-interest registry.** Let consumers register interest vectors;
  define the similarity threshold / top-k policy and where it is evaluated
  (in-MCP vs. a routing sidecar).
- **4c — Similarity-based fan-out, additive.** Route a copy of eligible messages
  to semantically matched consumers *in addition to* lexical routing (dual-route,
  flag-gated, observable) before anything depends on it.
- **4d — Promote semantic routing to primary** for the lanes where it proves out
  (Sigma first — it is the knowledge lane and already carries `embedding_ref`).

## Open questions

- Where does similarity matching run without becoming a latency/availability
  bottleneck on the hot `/send` path? (In-MCP vs. async sidecar.)
- How do replay/dedup/backpressure guards interact with fan-out to a *variable*
  set of recipients?
- Which lanes ever benefit from semantic routing vs. staying lexical (Alpha is a
  directed directive; Rho is control telemetry — both may stay lexical forever)?
- Source-of-truth alignment with the Holygrail
  `20_Semantic_Bus_Implementation_Guide.md` design intent.

## Out of scope

- Anything Stages 1–3 own (producers, control inversion, process topology).
- Replacing lexical routing wholesale — semantic routing is expected to be
  **additive and lane-selective**, not a hard cutover.
