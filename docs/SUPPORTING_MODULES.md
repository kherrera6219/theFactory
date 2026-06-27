# Supporting Modules Reference

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

This document covers the smaller orchestrator modules that did not yet have dedicated documentation. Each section maps to one or more source files.

---

## `migrations.py` and `migrations/` — Schema Migrations

**Source:** `services/orchestrator/orchestrator/migrations.py` + `migrations/` directory  
**Size:** ~4 KB combined

The migration subsystem applies incremental PostgreSQL schema changes using Alembic under the hood, driven by a custom runner that:

1. Takes a session-level advisory lock on the `missions` table to prevent concurrent migration runs
2. Runs all pending migration scripts in version order
3. Records applied versions in the `schema_migrations` table
4. Releases the advisory lock

### Entry Point

```python
migrations.apply_migrations(settings, connect=db_connect)
```

Called by `ensure_db_schema()` in `storage_core.py` during lifespan startup. The `connect` parameter is injectable for testing.

### Adding a Migration

1. Create a new file in `migrations/` named `VYYY_description.py` where `YYY` is the next sequential version number
2. Implement `upgrade(conn)` — receives an open psycopg connection in autocommit mode
3. Implement `downgrade(conn)` — required for all migrations
4. The runner detects and applies it on next startup

> **Never modify existing migration files.** Each file is content-addressed; the runner checksums applied scripts and will raise if a previously applied file changes.

---

## `auth.py` — Runtime Auth Enforcement

**Source:** `services/orchestrator/orchestrator/auth.py`  
**Size:** ~1.5 KB

Provides two FastAPI dependency functions used across all route modules:

| Dependency | Header | Credential | Used by |
|---|---|---|---|
| `require_api_key` | `X-API-Key` | `Settings.api_key` | `missions.py`, `operations.py` |
| `require_internal_key` | `X-Internal-Key` | `Settings.internal_service_key` | `internal.py` |

Both dependencies raise `HTTP 403 Forbidden` on mismatch. Neither implements rate limiting (that is handled at the API Gateway service, port 8100).

For the auth model rationale (API key vs. OIDC), see `ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`.

---

## `review_policy.py` — Human Review Escalation

**Source:** `services/orchestrator/orchestrator/review_policy.py`  
**Size:** ~1 KB

Defines the conditions under which a mission must be escalated to human review before proceeding to `VERIFIED` state.

```python
def requires_human_review(mission: MissionRecord) -> bool:
    ...
```

Returns `True` when any of the following conditions are met:

- `data_classification == TIER_3_REGULATED`
- `output_mode == APPLY_PATCH` and any `SecurityFinding` with severity `ERROR` or `CRITICAL` is present in `metadata["risk_assessment"]`
- `mission.metadata.get("force_human_review") == True` (operator override)
- The mission's `depth_mode == REGULATED`

When `True`, `mission_flow_v2/` halts progression from `GATING` to `FUSION` and emits `MISSION_COMPLETION_BLOCKED` with `reason: HUMAN_REVIEW_REQUIRED`. The mission remains in `GATING` until a review approval is written via `POST /internal/missions/{id}/review-approval`.

---

## `protocol.py` — Protocol Bus Message Schema

**Source:** `services/orchestrator/orchestrator/protocol.py`  
**Size:** ~4 KB

Defines the Pydantic models for all messages exchanged on the 6-stream Protocol Bus. Every message sent by `protocol_bus_producer.py` and consumed by `protocol_bus_consumer.py` must conform to these schemas.

### Message Envelope

```python
class BusMessage(BaseModel):
    message_id: str          # UUID v4
    stream: StreamName       # alpha | beta | delta | sigma | omega | rho
    event_type: str          # Free-form string, namespaced by stream
    mission_id: str | None
    agent_id: str | None
    payload: dict            # Stream-specific payload
    ts: str                  # UTC ISO-8601
    schema_version: str      # e.g., "1.0"
```

### Stream Assignment

| Stream | Purpose | Primary producers | Primary consumers |
|---|---|---|---|
| `alpha` | Mission state transitions | Orchestrator runtime, mission_flow_v2 | Dashboard service, mission control UI |
| `beta` | Agent coordination | Pod managers, specialist agents | Other agents, orchestrator |
| `delta` | LogicNode and artifact writes | Pod workers | Audit worker, knowledge lake |
| `sigma` | Security and compliance events | security_compliance.py, rqca_agent | Audit worker, compliance monitor |
| `omega` | System health and metrics | All services | Observability stack |
| `rho` | LLM cost and billing events | llm_delegation/cost_guard | LLM cost ledger |

For the full bus architecture, see `AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md`.

---

## `project_identity.py` — Project Namespace Stamping

**Source:** `services/orchestrator/orchestrator/project_identity.py`  
**Size:** ~1.6 KB

Provides two utilities used by `storage_missions.py` to assign and resolve a stable `project_id` for every mission.

```python
def resolve_project_id(metadata: dict, mission_id: str) -> str:
    """Derive a project_id from metadata or fall back to a deterministic hash of mission_id."""

def with_project_identity(metadata: dict, mission_id: str) -> dict:
    """Return metadata with project_id stamped in if not already present."""
```

**Derivation order:**
1. `metadata["project_id"]` if explicitly set by the caller
2. `metadata["__project_id__"]` if set by PM Agent during chartering
3. Deterministic hash of `mission_id[:8]` — ensures every mission always has a stable project namespace even when no explicit project is given

This guarantees `project_id` is never null in the database, simplifying aggregation queries in `storage_pods.summarize_projects()`.

---

## `hw_agent.py` — Hardware Awareness Agent

**Source:** `services/orchestrator/orchestrator/hw_agent.py`  
**Size:** ~2 KB

A lightweight support agent that detects the host's hardware capabilities at startup and writes them to `app.state.hw_profile` in `main.py`. The profile is consumed by `llm_delegation/router.py` to decide whether local model inference (Ollama) is viable.

Detects:
- Available VRAM (NVIDIA/Apple Silicon via platform-appropriate APIs)
- CPU core count and available RAM
- GPU model string
- Whether Ollama is reachable at `OLLAMA_BASE_URL`

The hardware profile is also included in the `GET /ops/health` response so operators can see whether the system is running in local-inference mode.

---

## `testdata_agent.py` — Test Data Generation Agent

**Source:** `services/orchestrator/orchestrator/testdata_agent.py`  
**Size:** ~4 KB

A specialist support agent that generates realistic test fixtures and mock data for the code produced by a mission. Called during `GATING` phase if `depth_mode` is `PRODUCTION` or `REGULATED`.

Outputs a **test data manifest** — a structured JSON document listing:
- Generated fixture files and their object-storage keys
- Mock API response payloads
- Seed data scripts for database-backed services
- Contract test stubs for external integrations

The manifest is persisted via `storage_artifacts.insert_testdata_manifest()` and included in the evidence bundle.

---

## `system_maintenance.py` — Maintenance Mode

**Source:** `services/orchestrator/orchestrator/system_maintenance.py`  
**Size:** ~3 KB

Provides a soft maintenance mode that pauses new mission intake without interrupting running missions.

```python
def enter_maintenance_mode(reason: str) -> None: ...
def exit_maintenance_mode() -> None: ...
def is_in_maintenance_mode() -> bool: ...
```

When `is_in_maintenance_mode()` returns `True`:
- `POST /missions` returns `HTTP 503 Service Unavailable` with the maintenance reason in the response body
- The runtime intake loop skips queue pickup
- Running missions continue to completion
- `GET /ops/health` includes `"maintenance": true` and the reason string

Maintenance state is held in a module-level boolean — it is **not** persisted to the database. A restart clears maintenance mode. For DR scenarios requiring persistent maintenance, see `DEPLOYMENT_DR_PLAYBOOK.md`.

---

## `agent_integrations.py` — Integration Catalog Agent

**Source:** `services/orchestrator/orchestrator/agent_integrations.py`  
**Size:** ~15 KB

Implements the Integration Standards (IS) Agent (AGENT-07-IS), which maintains a catalog of all external service integrations that missions may produce or consume. Operates alongside the IS Agent documented in `IS_AGENT.md`.

Responsibilities:
- Maintains a registry of known integration patterns (REST, gRPC, message queue, file-based, database)
- Validates generated integration code against the catalog before `VERIFIED` state
- Produces integration compliance findings included in the audit report
- Flags integrations that require additional review (PCI-DSS adjacent, HIPAA-adjacent, government APIs)

The integration catalog is seeded from `knowledge_lake.py` on the `fetch` state and updated with new patterns discovered during each mission.
