# Knowledge Lake and Embeddings

Last updated: 2026-06-13

Document version: 2026.06.11  
Status: Canonical  
Audience: Developers and architects

## Overview

The **Knowledge Lake** is theFactory's runtime semantic memory. It is an abstraction layer over three vector stores (Qdrant, Milvus, Neo4j) and one relational store (PostgreSQL) that allows all agents to read from and write to a shared, mission-scoped knowledge graph without coupling to any single backend. The **Embeddings** module provides the vector generation pipeline that populates the lake.

## Code Locations

| File | Size | Role |
|---|---|---|
| `services/orchestrator/orchestrator/knowledge_lake.py` | 19 KB | Knowledge Lake abstraction and query interface |
| `services/orchestrator/orchestrator/knowledge_embeddings.py` | 9 KB | Embedding pipeline (chunking, model dispatch, upsert) |

## Architecture

```
  Agents / Mission Flow v2
          │
          ▼
   KnowledgeLake (knowledge_lake.py)
     ├── write(node, namespace)     → routes to correct backend
     ├── query(query, namespace)    → fan-out + re-rank
     ├── get_graph(mission_id)      → Neo4j traversal
     └── purge(mission_id)         → coordinated TTL eviction
          │
          ├──► Qdrant (qdrant_store.py)       ← semantic similarity search
          ├──► Milvus (milvus_store.py)        ← high-throughput vector ops
          ├──► Neo4j  (neo4j_store.py)         ← graph traversal and relationship queries
          └──► PostgreSQL (storage_core.py)    ← authoritative record store

  KnowledgeEmbeddings (knowledge_embeddings.py)
     ├── chunk(text)                → token-aware chunking
     ├── embed(chunks)              → model dispatch (local or API)
     └── upsert(vectors, store)     → fan-out write to Qdrant + Milvus
```

## Knowledge Lake API

### `write(node: KnowledgeNode, namespace: str) → str`

Persists a `KnowledgeNode` to the appropriate store(s) determined by node type:

| Node type | Primary store | Secondary store |
|---|---|---|
| `LOGICNODE` | Qdrant | PostgreSQL |
| `DEPENDENCY` | Milvus | PostgreSQL |
| `RELATIONSHIP` | Neo4j | — |
| `DOCUMENT` | Qdrant | PostgreSQL |
| `ARTIFACT` | PostgreSQL | Object Store |

### `query(query: str, namespace: str, top_k: int = 10) → list[KnowledgeResult]`

Issues a semantic query. The lake fans out to Qdrant and Milvus in parallel, merges results by cosine similarity score, re-ranks using the mission's AIM context, and returns the top-k results.

### `get_graph(mission_id: str) → KnowledgeGraph`

Returns the full Neo4j subgraph for a mission — nodes, edges, and relationship types.

### `purge(mission_id: str)`

Evicts all vectors, graph nodes, and PostgreSQL records scoped to the mission. Called by the lifecycle recovery module on mission tombstone.

## Key Dataclasses

```python
@dataclass
class KnowledgeNode:
    node_id: str
    node_type: Literal["LOGICNODE", "DEPENDENCY", "RELATIONSHIP", "DOCUMENT", "ARTIFACT"]
    content: str
    metadata: dict
    namespace: str           # usually mission_id
    embedding: list[float] | None  # populated by KnowledgeEmbeddings before write

@dataclass
class KnowledgeResult:
    node_id: str
    node_type: str
    content: str
    score: float             # cosine similarity [0.0, 1.0]
    source_store: str        # "qdrant" | "milvus" | "neo4j"
```

## Embedding Pipeline

`knowledge_embeddings.py` performs three steps before every `write` call:

1. **Chunking** — splits content into overlapping token windows (default 512 tokens, 64-token overlap). Uses a tokenizer matched to the active embedding model.
2. **Model dispatch** — selects embedding model from `settings.py` → `EMBEDDING_MODEL`. Supports local `sentence-transformers` models and OpenAI `text-embedding-3-small/large`. Falls back to local model when `LLM_OFFLINE_MODE=true`.
3. **Upsert** — writes chunk vectors to Qdrant (primary) and Milvus (secondary) with the `node_id` and `namespace` as payload metadata.

## Namespace Isolation

Every write and query is scoped to a `namespace` (typically `mission_id`). This prevents cross-mission data bleed. The purge operation uses namespace as the eviction key across all stores.

## Configuration (`settings.py` keys)

| Key | Default | Description |
|---|---|---|
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model name |
| `KNOWLEDGE_LAKE_TOP_K` | `10` | Default query result count |
| `KNOWLEDGE_LAKE_CHUNK_SIZE` | `512` | Token window size for chunking |
| `KNOWLEDGE_LAKE_CHUNK_OVERLAP` | `64` | Overlap window in tokens |
| `KNOWLEDGE_LAKE_RERANK_ENABLED` | `true` | Enable AIM-context re-ranking |

## Operational Notes

- Query latency is reported on the Grafana **Knowledge Lake Query Latency** panel (p50/p95/p99).
- Namespace purge failures are logged at `ERROR` level and retried once on the next lifecycle recovery cycle.
- Milvus is optional: if `MILVUS_ENABLED=false`, all vector writes go to Qdrant only.
