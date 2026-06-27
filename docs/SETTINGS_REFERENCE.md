# Settings Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical

**Code file:** `services/orchestrator/orchestrator/settings.py`  
**Audience:** Developers, Operators  
**Last reviewed:** 2026-06-11

This document is the canonical reference for the `Settings` dataclass and the `load_settings()` factory function that hydrates it from environment variables. Every configuration knob available to the orchestrator is documented here.

---

## Overview

`settings.py` exposes a single frozen `Settings` dataclass that is instantiated once at startup via `load_settings()` and stored on `app.state.settings`. All orchestrator code receives settings by dependency injection — no module reads `os.getenv()` directly outside this file.

The design follows three rules:
1. **Frozen at startup** — `@dataclass(frozen=True)` prevents accidental mutation after boot.
2. **Fail-fast in production** — `load_settings()` raises `RuntimeError` if `ENVIRONMENT=production` and no API key is configured.
3. **Sensible dev defaults** — every field has a development-safe default so `docker compose up` works with an empty `.env`.

---

## Environment Detection

`load_settings()` reads `ENVIRONMENT` (default: `development`) and uses it to drive two security guardrails:

| Condition | Behaviour |
|---|---|
| `ENVIRONMENT=production` and no API keys set | `RuntimeError` raised — orchestrator refuses to start |
| `ENVIRONMENT=production` and `AGENT_SERVICE_KEY_MODE=shared` | `WARNING` logged — all agents share one identity |
| `ENVIRONMENT=production` and `LANGGRAPH_FAIL_OPEN=true` | `WARNING` logged — LangGraph errors silently fall back to legacy engine |
| Any other environment | Defaults accepted, no guardrails |

---

## Field Reference

### Infrastructure

| Field | Env Var | Default | Description |
|---|---|---|---|
| `redis_url` | `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL for all streams and caching |
| `postgres_url` | `POSTGRES_URL` | `postgresql://postgres:postgres@postgres:5432/ulr` | Primary Postgres URL (may be PgBouncer) |
| `migration_postgres_url_override` | `MIGRATION_POSTGRES_URL` | `""` | Direct Postgres URL for migrations. Must bypass PgBouncer transaction pooling (session advisory lock required). Falls back to `postgres_url` when empty. |
| `db_pool_min_size` | `DB_POOL_MIN_SIZE` | `2` | asyncpg connection pool minimum |
| `db_pool_max_size` | `DB_POOL_MAX_SIZE` | `10` | asyncpg connection pool maximum |

### Streams and Consumers

| Field | Env Var | Default | Description |
|---|---|---|---|
| `intake_stream` | `INTAKE_STREAM` | `missions.intake` | Redis Stream key for incoming missions |
| `state_stream` | `STATE_STREAM` | `missions.state` | Redis Stream key for state change events |
| `max_stream_len` | `MAX_STREAM_LEN` | `20000` | MAXLEN cap on both streams |
| `consumer_group` | `MISSION_CONSUMER_GROUP` | `orchestrator` | Redis consumer group name |
| `consumer_name` | `MISSION_CONSUMER_NAME` | `orchestrator-{hostname}` | Unique consumer identity within the group |
| `intake_dlq_stream` | `INTAKE_DLQ_STREAM` | `factory:dlq:intake-stream` | Dead-letter queue stream for unprocessable intake messages |
| `intake_dlq_max_len` | `INTAKE_DLQ_MAX_LEN` | `1000` | MAXLEN cap on DLQ stream |
| `stale_consumer_idle_ms` | `STALE_CONSUMER_IDLE_MS` | `300000` | Idle threshold (ms) before a consumer is considered stale |
| `stale_consumer_reap_interval_seconds` | `STALE_CONSUMER_REAP_INTERVAL_SECONDS` | `3600` | How often the stale consumer reaper runs |

### Mission Flow and Auto-Transition

| Field | Env Var | Default | Description |
|---|---|---|---|
| `auto_transition_enabled` | `AUTO_TRANSITION_ENABLED` | `true` | Whether the orchestrator automatically advances mission state |
| `transition_step_seconds` | `TRANSITION_STEP_SECONDS` | `1.0` | Polling interval for the auto-transition loop |
| `mission_flow_v2_enabled` | `MISSION_FLOW_V2_ENABLED` | `true` | Use Mission Flow v2 (11-phase state machine) as the default engine |
| `intake_topic` | `INTAKE_TOPIC` | `intake.feature_contract.created` | Protocol Bus topic for new intake events |
| `default_priority` | `DEFAULT_EVENT_PRIORITY` | `NORMAL` | Default mission priority when none is supplied |
| `producer_name` | `ORCHESTRATOR_PRODUCER` | `orchestrator` | Producer identity on all stream messages |

### Feature Flags

| Field | Env Var | Default | Description |
|---|---|---|---|
| `mission_equivalence_enforcement_enabled` | `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED` | `false` | Enforce equivalence verification before completing missions |
| `mission_equivalence_python_execution_enabled` | `MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED` | `false` | Allow Python sandbox execution during equivalence checks |
| `mission_security_compliance_enforcement_enabled` | `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` | `false` | Enforce data-classification and security-compliance rules |
| `testdata_agent_enabled` | `TESTDATA_AGENT_ENABLED` | `false` | Enable the TestData agent (AGENT-40) |
| `rqca_agent_enabled` | `RQCA_AGENT_ENABLED` | `false` | Enable the RQCA agent (AGENT-41) |
| `rqca_enforcement_enabled` | `RQCA_ENFORCEMENT_ENABLED` | `false` | Fail missions that do not pass RQCA checks |
| `rqca_test_command_template` | `RQCA_TEST_COMMAND_TEMPLATE` | `""` | Per-language shell template for RQCA test execution. `{filename}` and `{test_filename}` are substituted at runtime. |
| `docker_bin` | `DOCKER_BIN` | `docker` | Docker binary used by RQCA for sandboxed execution |
| `depabs_execution_enabled` | `DEPABS_EXECUTION_ENABLED` | `false` | Enable DEPABS live dependency resolution (experimental) |
| `port_two_phase_enabled` | `PORT_TWO_PHASE_ENABLED` | `false` | Enable two-phase PORT mission processing |
| `llm_safety_block_enabled` | `LLM_SAFETY_BLOCK_ENABLED` | `false` | Hard-block missions that trigger LLM safety filters |

### LangGraph

| Field | Env Var | Default | Description |
|---|---|---|---|
| `langgraph_enabled` | `LANGGRAPH_ENABLED` | `false` | Use LangGraph as the mission orchestration engine instead of v2 |
| `langgraph_fail_open` | `LANGGRAPH_FAIL_OPEN` | `true` (dev) / `false` (prod) | If `true`, LangGraph errors fall back to the legacy engine silently. In production, defaults to `false` (fail-closed). |
| `langgraph_checkpointer` | `LANGGRAPH_CHECKPOINTER` | `none` | Checkpointer backend: `none`, `memory`, or `postgres` |
| `langgraph_thread_prefix` | `LANGGRAPH_THREAD_PREFIX` | `mission` | Prefix for LangGraph thread IDs |
| `langgraph_checkpointer_postgres_url` | `LANGGRAPH_CHECKPOINTER_POSTGRES_URL` | `""` | Dedicated Postgres URL for LangGraph checkpointer (direct, not PgBouncer) |
| `langgraph_checkpointer_setup` | `LANGGRAPH_CHECKPOINTER_SETUP` | `false` | Run checkpointer schema setup on startup |
| `langgraph_checkpoint_namespace` | `LANGGRAPH_CHECKPOINT_NAMESPACE` | `""` | Namespace prefix for checkpoint keys |

### Qdrant (Vector Store — Primary)

| Field | Env Var | Default | Description |
|---|---|---|---|
| `qdrant_url` | `QDRANT_URL` | `http://qdrant:6333` | Qdrant service URL |
| `qdrant_api_key` | `QDRANT_API_KEY` | `""` | Optional Qdrant API key |
| `qdrant_enabled` | `QDRANT_ENABLED` | `true` | Enable Qdrant integration (also requires URL to be set) |
| `qdrant_collection` | `QDRANT_COLLECTION` | `mission_knowledge` | Collection name |
| `qdrant_vector_size` | `QDRANT_VECTOR_SIZE` | `256` | Embedding vector dimension |
| `qdrant_timeout_seconds` | `QDRANT_TIMEOUT_SECONDS` | `3.0` | Per-request timeout |

### Milvus (Vector Store)

| Field | Env Var | Default | Description |
|---|---|---|---|
| `milvus_uri` | `MILVUS_URI` | `http://milvus:19530` | Milvus URI |
| `milvus_token` | `MILVUS_TOKEN` | `""` | Milvus authentication token |
| `milvus_enabled` | `MILVUS_ENABLED` | `true` | Enable Milvus (on by default) |
| `milvus_collection` | `MILVUS_COLLECTION` | `mission_knowledge` | Collection name |
| `milvus_vector_size` | `MILVUS_VECTOR_SIZE` | `64` | Embedding vector dimension |
| `milvus_timeout_seconds` | `MILVUS_TIMEOUT_SECONDS` | `3.0` | Per-request timeout |

### Neo4j (Graph Store)

| Field | Env Var | Default | Description |
|---|---|---|---|
| `neo4j_url` | `NEO4J_URL` | `http://neo4j:7474` | Neo4j HTTP URL |
| `neo4j_enabled` | `NEO4J_ENABLED` | `true` | Enable Neo4j integration (on by default) |
| `neo4j_username` | `NEO4J_USERNAME` | `neo4j` | Auth username |
| `neo4j_password` | `NEO4J_PASSWORD` | `""` | Auth password |
| `neo4j_database` | `NEO4J_DATABASE` | `neo4j` | Target database name |
| `neo4j_timeout_seconds` | `NEO4J_TIMEOUT_SECONDS` | `3.0` | Per-request timeout |

### Object Storage (MinIO/S3)

| Field | Env Var | Default | Description |
|---|---|---|---|
| `object_storage_enabled` | `OBJECT_STORAGE_ENABLED` | `true` | Enable S3-compatible object storage (on by default) |
| `object_storage_endpoint` | `OBJECT_STORAGE_ENDPOINT` | `http://minio:9000` | S3-compatible endpoint |
| `object_storage_access_key` | `OBJECT_STORAGE_ACCESS_KEY` | `""` | Access key |
| `object_storage_secret_key` | `OBJECT_STORAGE_SECRET_KEY` | `""` | Secret key |
| `object_storage_bucket` | `OBJECT_STORAGE_BUCKET` | `mission-audit-artifacts` | Target bucket |
| `object_storage_prefix` | `OBJECT_STORAGE_PREFIX` | `missions` | Key prefix for all stored objects |
| `object_storage_region` | `OBJECT_STORAGE_REGION` | `us-east-1` | Storage region |
| `object_storage_timeout_seconds` | `OBJECT_STORAGE_TIMEOUT_SECONDS` | `5.0` | Per-request timeout |
| `object_storage_retention_days` | `OBJECT_STORAGE_RETENTION_DAYS` | `90` | Object retention period (days) |
| `object_storage_size_threshold_bytes` | `OBJECT_STORAGE_SIZE_THRESHOLD_BYTES` | `524288` | Artifacts above 512 KB are offloaded to S3; smaller ones stay in Postgres |
| `object_storage_legal_hold_on_fail` | `OBJECT_STORAGE_LEGAL_HOLD_ON_FAIL` | `true` | Apply S3 Object Lock legal hold to failed-mission artifacts |
| `object_storage_force_path_style` | `OBJECT_STORAGE_FORCE_PATH_STYLE` | `true` | Use path-style URLs (required for MinIO) |
| `object_storage_require_tls` | `OBJECT_STORAGE_REQUIRE_TLS` | `false` | Reject non-TLS storage endpoints. Production Compose sets this to `true`; set `OBJECT_STORAGE_ENDPOINT` to an HTTPS S3-compatible endpoint in production. |

### Knowledge Embeddings

| Field | Env Var | Default | Description |
|---|---|---|---|
| `knowledge_embedding_provider` | `KNOWLEDGE_EMBEDDING_PROVIDER` | `gemini` | Embedding model provider: `gemini` or `openai` |
| `knowledge_embedding_model` | `KNOWLEDGE_EMBEDDING_MODEL` | `""` | Override embedding model name. When empty, the provider default is used (`gemini-embedding-001` for Gemini, `text-embedding-3-small` for OpenAI). |
| `knowledge_embedding_timeout_seconds` | `KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS` | `10.0` | Per-request embedding timeout |
| `knowledge_refresh_enabled` | `KNOWLEDGE_REFRESH_ENABLED` | `true` | Enable periodic Knowledge Lake refresh |
| `knowledge_refresh_interval_seconds` | `KNOWLEDGE_REFRESH_INTERVAL_SECONDS` | `3600` | Interval between refresh cycles |

### Authentication and API Keys

| Field | Env Var | Default | Description |
|---|---|---|---|
| `admin_api_key` | `ORCHESTRATOR_ADMIN_API_KEY` | `""` | Grants `admin`, `mutate`, `internal`, `read` roles |
| `internal_service_api_key` | `INTERNAL_SERVICE_API_KEY` | `""` | Grants `worker`, `mutate`, `internal`, `read` roles |
| `readonly_api_key` | `ORCHESTRATOR_READONLY_API_KEY` | `""` | Grants `read` role only |
| `extra_api_keys` | `ORCHESTRATOR_API_KEYS` | `""` | Semicolon-separated `key=role1,role2` entries for additional keys |
| `agent_service_key_mode` | `AGENT_SERVICE_KEY_MODE` | `shared` | `shared` — agents fall back to the shared service key. `strict` — each agent must have its own dedicated key. |

The computed property `api_key_roles` merges all key sources into a `dict[str, set[str]]` used by the auth middleware. The computed property `agent_service_api_keys` reads `AGENT_SERVICE_API_KEYS` (format: `AGENT_ID:key;AGENT_ID:key`) and validates every key against the live agent registry.

### Protocol Bus

| Field | Env Var | Default | Description |
|---|---|---|---|
| `protocol_bus_url` | `PROTOCOL_BUS_URL` | `http://protocol-bus-mcp:8090` | In-network URL for the Protocol Bus MCP service |
| `protocol_bus_api_key` | `PROTOCOL_BUS_API_KEY` (or `MCP_API_KEY`) | `""` | Shared HMAC key validated by the bus. `MCP_API_KEY` is accepted as a backward-compatible alias. |
| `protocol_bus_consumer_enabled` | `PROTOCOL_BUS_CONSUMER_ENABLED` | `true` | Whether the orchestrator starts a Protocol Bus consumer |

### Observability

| Field | Env Var | Default | Description |
|---|---|---|---|
| `audit_retention_days` | `AUDIT_RETENTION_DAYS` | `90` | Days to retain audit records in Postgres |

### Topology

| Field | Env Var | Default | Description |
|---|---|---|---|
| `topology_mode` | `TOPOLOGY_MODE` | `condensed` | Active Compose profile. `condensed` = shared pod workers. `dedicated` = one container per pod manager. `full-dedicated` = one container per language specialist. |

### Agent Scaling

| Field | Env Var | Default | Description |
|---|---|---|---|
| `agent_scaling_enabled` | `AGENT_SCALING_ENABLED` | `false` | Enable dynamic agent instance scaling |
| `agent_scaling_max_instances` | `AGENT_SCALING_MAX_INSTANCES` | `4` | Maximum agent instances per role (capped at 8) |
| `agent_scaling_items_per_instance` | `AGENT_SCALING_ITEMS_PER_INSTANCE` | `3` | Target queue depth per instance before scaling |

### Schema Paths

| Field | Env Var | Default | Description |
|---|---|---|---|
| `event_schema_path` | `EVENT_SCHEMA_PATH` | `schemas/event.envelope.schema.json` | Path to the event envelope JSON schema |
| `logicnode_schema_path` | `LOGICNODE_SCHEMA_PATH` | `schemas/logicnode.schema.json` | Path to the LogicNode JSON schema |
| `topics_path` | `TOPICS_PATH` | `protocol/topics.yaml` | Path to the Protocol Bus topics definition |

---

## Computed Properties

### `migration_postgres_url`
Returns `migration_postgres_url_override` if set, otherwise falls back to `postgres_url`. Used exclusively by `storage_core.py` during schema migration runs to bypass PgBouncer's transaction-mode connection pooling, which drops session-level advisory locks between statements.

### `api_key_roles`
Merges all API key sources (admin, internal, readonly, extra, per-agent) into a single `dict[str, set[str]]`. This dict is the sole input to the auth middleware's role resolution.

### `agent_service_api_keys`
Delegates to `configured_agent_service_key_map()` in `shared_runtime.agent_keys`, validating all parsed agent IDs against the live `AGENT_REGISTRY` set. Keys for unrecognised agent IDs are rejected at startup.

### `topic_for_state(state_value)`
Maps a `MissionState` string value to its corresponding Protocol Bus topic:

| State | Topic env var | Default topic |
|---|---|---|
| `RUNNING` | `STATE_TOPIC_RUNNING` | `fusion.requested` |
| `VERIFIED` | `STATE_TOPIC_VERIFIED` | `artifact.rir.verified` |
| `COMPLETE` | `STATE_TOPIC_COMPLETE` | `mission.state.complete` |
| `FAILED` | `STATE_TOPIC_FAILED` | `incident.runtime.errorlog` |
| *(any other)* | `STATE_TOPIC_QUEUED` | value of `intake_topic` |

---

## Production Hardening Checklist

Before deploying to production, verify the following:

- [ ] `ENVIRONMENT=production` set
- [ ] At least one of `ORCHESTRATOR_ADMIN_API_KEY`, `INTERNAL_SERVICE_API_KEY`, or `ORCHESTRATOR_READONLY_API_KEY` is set
- [ ] `AGENT_SERVICE_KEY_MODE=strict` — each agent has its own service key
- [ ] `LANGGRAPH_FAIL_OPEN=false` (if LangGraph is enabled)
- [ ] `MIGRATION_POSTGRES_URL` points directly to Postgres (not PgBouncer)
- [ ] `OBJECT_STORAGE_REQUIRE_TLS=true` for production object storage, with `OBJECT_STORAGE_ENDPOINT=https://...`
- [ ] `OBJECT_STORAGE_LEGAL_HOLD_ON_FAIL=true` (default) — do not disable without compliance sign-off
- [ ] `AUDIT_RETENTION_DAYS` set to meet your compliance requirement (default 90)

---

## Related Documentation

- [ORCHESTRATOR_MAIN.md](ORCHESTRATOR_MAIN.md) — how `app.state.settings` is initialised at startup
- [STORAGE_LAYER.md](STORAGE_LAYER.md) — uses `migration_postgres_url` for schema migrations
- [LLM_DELEGATION.md](LLM_DELEGATION.md) — reads LangGraph and embedding settings
- [AGENT_SERVICE_KEY_ISOLATION.md](AGENT_SERVICE_KEY_ISOLATION.md) — `agent_service_key_mode` enforcement detail
- [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md) — `audit_retention_days` and metrics pipeline
- [TRACING.md](TRACING.md) — OTEL tracing config (companion to this file)
