# Supporting Modules Reference

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers and operators

This document covers the smaller orchestrator modules that did not yet have dedicated documentation. Each section maps to one or more source files. Every section below was re-verified against the current source on 2026-07-03 as part of a full documentation audit — several prior sections (`auth.py`, `system_maintenance.py`, `agent_integrations.py`) described functions/classes that never existed and have been rewritten from the real code.

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

## `auth.py` — Role-Based API Key Auth

**Source:** `services/orchestrator/orchestrator/auth.py`

Provides a single FastAPI dependency factory, `require_roles(settings, allowed_roles)`, built on a role-tagged API key map (`Settings.api_key_roles: dict[str, set[str]]`). Each configured key carries a set of roles (e.g. `{"read"}`, `{"mutate", "admin", "worker"}`); the dependency:

1. Reads the `X-API-Key` header — 401 if missing.
2. Matches it against every configured key using `hmac.compare_digest` (constant-time; every key is checked regardless of match to avoid leaking which key matched via early-exit timing).
3. 401 if no configured key matches.
4. 403 if the matched key's roles don't intersect `allowed_roles`.
5. Returns an `AuthContext(api_key, roles)` frozen dataclass for the route to use.

`services/orchestrator/orchestrator/main.py` builds three pre-configured dependencies from this factory — `READ_AUTH` (role `read`), `MUTATION_AUTH` (roles `mutate`/`admin`/`worker`), `INTERNAL_AUTH` (role `internal`) — re-exported by `routes/_deps.py` as `READ_AUTH_DEP`/`MUTATION_AUTH_DEP`/`INTERNAL_AUTH_DEP` for use across `missions.py`, `operations.py`, and `internal.py`.

Rate limiting is handled at the API Gateway service (port 8100), not here.

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

For the full bus architecture, see `PROTOCOL_BUS_PROGRAM_ROADMAP.md`.

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

## `system_maintenance.py` — Backup and Diagnostic Bundles

**Source:** `services/orchestrator/orchestrator/system_maintenance.py`

Implements the `MaintenanceManager` class (constructed once per app via `get_maintenance_manager(app)`), which backs the `/internal/maintenance/*` routes:

```python
class MaintenanceManager:
    def __init__(self, settings: Any): ...
    async def create_diagnostic_bundle(self, mission_id: str | None = None) -> str: ...
```

`create_diagnostic_bundle()` writes a `.tar.gz` under `FACTORY_DATA_ROOT/diagnostics/` containing:
- `system_status.json` — timestamp, version, OS, and the optional `mission_id` context
- `environment_sanitized.json` — every process env var, **except**:
  - names containing `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIAL`, or `_ROLE_ID`
  - any remaining value gets its URL userinfo segment redacted too (e.g. `postgresql://user:***@host/db`), since connection-string env vars embed a plaintext password regardless of the variable's own name

`run_full_backup()` is the manager's other responsibility: it tars up `FACTORY_DATA_ROOT/stores/` (the mapped Postgres/Qdrant/etc. volume mount point) into `FACTORY_DATA_ROOT/backups/factory-full-backup-<timestamp>.tar.gz`. There is no maintenance-mode toggle that pauses mission intake in this module — for planned downtime, stop the intake loop or the service itself; see `DEPLOYMENT_DR_PLAYBOOK.md`.

---

## `agent_integrations.py` — Agent Integration Snapshot Builder

**Source:** `services/orchestrator/orchestrator/agent_integrations.py`

Builds a static, derived-from-`AGENT_REGISTRY` snapshot describing how every one of the 41 agents integrates with the rest of the system — not a runtime integration-catalog agent. Key functions:

```python
def build_agent_integration_record(agent: AgentDefinition) -> dict[str, Any]: ...
def build_agent_integrations_snapshot() -> dict[str, Any]: ...
```

For each `AgentDefinition`, `build_agent_integration_record()` derives:
- `protocols` — communication protocols the agent participates in
- `protocol_bus` — its Protocol Bus `publish_topics`/`consume_topics` bindings
- `data_systems` — which stores (Postgres, Qdrant, Neo4j, object storage) it reads/writes
- `llm_recommendation` — its default LLM provider/model routing
- `persona_profile` — assembled via `agent_personas.build_agent_persona_profile()`

`build_agent_integrations_snapshot()` runs this over every agent in `AGENT_REGISTRY` and aggregates the distinct protocol/store sets used across the whole system. This snapshot is what backs the `GET /v1/operations/agent-integrations` endpoint — it's a read-only reflection of the static agent registry, not a code-validation or compliance-catalog agent.

---

## `port_coordinator.py` — PORT Two-Phase Mission Setup

**Source:** `services/orchestrator/orchestrator/port_coordinator.py`

Coordinates the two-phase flow for `PORT`-type missions (porting source code from one language to another). `PORT_TWO_PHASE_ENABLED` defaults **true** (Python and compose). This is not a network port allocator — the name refers to code *porting*.

```python
def _setup_port_two_phase(metadata: dict, mission: Any, clusters: list[dict] | None) -> None: ...
async def run_port_extraction_phase(*, mission_id: str, mission: Any, metadata: dict, settings: Any) -> dict[str, Any]: ...
```

- `_setup_port_two_phase()` runs after CEO delegation. It detects the source language from the uploaded bundle/prompt, resolves the target language from the mission's `requested_target_language`, sets `metadata["port_phase"] = "extraction"`, and picks a source-language pod manager/specialist (preferring an explicit `source_extraction` cluster from CEO decomposition, falling back to the language's default pod/specialist).
- `run_port_extraction_phase()` runs the first time `_prepare_specialist_plan` (`mission_flow_v2/phases_build.py`) sees `port_phase == "extraction"`. It generates an AIM and a specialist plan for the *source* language, extracts LogicNode-shaped concepts from the AIM's file entries, appends a `MISSION_PORT_EXTRACTION_COMPLETE` chain event, and returns `port_source_logicnodes`/`port_source_aim`/`port_source_plan` plus `port_phase: "generation"` (so the next re-entry into `_prepare_specialist_plan` takes the generation path instead). The caller in `phases_build.py` guards against re-running this a second time while `port_phase` is still `"extraction"` via `_chain_event_exists(metadata, "MISSION_PORT_EXTRACTION_COMPLETE")` — without that guard, a retry would re-run two LLM calls and mint fresh non-deterministic extraction results.
- AIM generation and specialist-plan generation failures are individually caught and degrade to a `{"source": "error"/"fallback"}` marker rather than raising; `extraction_degraded` in the returned dict reflects whether either step degraded.

---

## `equivalence_verifier.py` — PORT/Build Output Contract Checks

**Source:** `services/orchestrator/orchestrator/equivalence_verifier.py`

A deterministic, static (no code execution) contract checker that produces the `equivalence_report` consumed by the `GATING`/delivery phases. Entry point:

```python
def build_equivalence_report(*, mission_id: str, requested_target_language: str | None, metadata: dict, build_artifacts: list[dict], enforcement_enabled: bool) -> dict[str, Any]: ...
```

Runs a fixed set of named checks against the mission's generated output and metadata — each check returns a status (`pass`/`warn`/`fail`) and a `required` flag. Required checks include `generated_output_exists`, `generated_artifact_verified`, `artifact_format_matches_contract`, `language_alignment`, and `language_content_signature` (a regex-based detector added after a real incident where an LLM silently fell back to generating Python for a non-Python target — it flags syntactic tells of the wrong language in the generated text, independent of the LLM's own self-reported `language` field, though it currently only covers ~8 of the ~19 supported target languages). Advisory-only (`required=False`) checks include keyword-based acceptance-criteria and PORT source-concept coverage heuristics — these can produce false "covered" verdicts on superficial keyword overlap, but since they're non-required they cannot flip the report's `passed`/`blocking` verdict. `report["blocking"]` is `True` only when a required check fails **and** `enforcement_enabled` is set (`mission_equivalence_enforcement_enabled`, default `false`).

Since Phase 5 this report can carry a second, separate section — see `equivalence_execution.py` below. The two scopes are kept distinct rather than merged into one check list, so a strong result in one cannot silently compensate for a weak result in the other.

---

## `sandbox_exec.py` — Shared Hardened Execution Sandbox

**Source:** `services/orchestrator/orchestrator/sandbox_exec.py`

**Every execution of untrusted generated code in this system goes through this module.** RQCA runtime QC and behavioural equivalence both call `run_in_sandbox`; neither builds its own `docker run` command line, and a test enforces that.

```python
async def run_in_sandbox(*, docker_bin: str, workspace_dir: str | Path, base_image: str, command: str, timeout_seconds: int = 30, memory_mb: int = 256) -> SandboxResult: ...
```

`SANDBOX_SECURITY_FLAGS` is the single source of truth for the container hardening: `--network=none` (no exfiltration or further payload fetch), `--read-only` plus a `:ro` workspace mount (a sample cannot rewrite the artifact it is being judged against), `--tmpfs=/tmp:size=64m,mode=1777` (the one writable location, capped and discarded), `--cap-drop=ALL` and `--security-opt=no-new-privileges:true` (no capabilities, no regaining them via setuid), and `--memory` / `--memory-swap=0` / `--cpus=1` (bounded blast radius; disabling swap prevents trading memory pressure for unbounded disk).

**Do not relax any of these, and do not add a second execution path.** Callers may request *less* than `MAX_TIMEOUT_SECONDS` (60) and `MAX_MEMORY_MB` (512), never more — requests are clamped, and unparseable values fall back to the default rather than to "unlimited". A timeout returns `timed_out=True` rather than raising, so a hostile or slow sample degrades to a recorded non-result.

`build_sandbox_args` is exposed separately so tests can assert the flags without a Docker daemon.

---

## `equivalence_execution.py` — Behavioural Equivalence by Execution

**Source:** `services/orchestrator/orchestrator/equivalence_execution.py`

Adds `verification_scope: "behavioural"` alongside `equivalence_verifier.py`'s `"correctness"`. It invokes the generated artifact with the argument vectors Phase 4 attached to the mission's Refined-IR, inside `sandbox_exec`, and records what happened.

Gated on `mission_equivalence_python_execution_enabled` (default `false`; flag off ⇒ the equivalence report is byte-identical). Python only — other languages record an honest `skipped`. Docker unavailable records `skipped`, **never** `passed`.

**Counting is deliberately conservative, and this matters more than the numbers:**

| Outcome | Meaning |
|---|---|
| `passed` | The vector had a recorded expected output **and** the artifact matched it |
| `executed_without_error` | The function ran on those inputs. Evidence it executes — **not** evidence it is correct |
| `failed` | Mismatched a recorded expectation, raised, or the artifact would not import |
| `skipped` | Timed out, function absent, or nothing to execute — a non-result, not a verdict |

Phase 4 leaves `out.expected` as `null` on purpose, because the expected output is unknowable without execution. Promoting `executed_without_error` to `passed` would improve every figure on the report while recreating exactly the "check that can never fail" this work removed. Per UPG-53 behavioural results are advisory — they do not touch the correctness report's `status`/`passed`/`blocking` — until pass rates have been measured across real missions.

The driver injects argument values via `json.loads` of an embedded literal rather than interpolating them into source, and reads only a sentinel-prefixed line from stdout, so neither a hostile vector value nor arbitrary artifact output can influence the verdict.

---

## `is_agent.py` — Knowledge Lake Language Bootstrap

**Source:** `services/orchestrator/orchestrator/is_agent.py`

Despite the filename, this is not a standalone "Integration Specialist" agent class — it seeds static per-language reference documents into the Knowledge Lake and detects which languages a mission's source/prompt actually touches.

```python
def detect_required_languages(prompt: str, source_code: str | None) -> set[str]: ...
def _bootstrap_content_for_language(language_key: str) -> dict[str, Any]: ...
```

`detect_required_languages()` combines prompt-text keyword matching with source-code heuristics (e.g. a `^import [A-Z]|^package [a-z]` regex for Java/Kotlin/Scala-style import/package statements) to decide which language reference docs a mission needs. `_bootstrap_content_for_language()` (backed by the static `_BOOTSTRAP_DOCS` table) produces the actual reference-doc content, which is upserted into the Knowledge Lake via `_upsert_knowledge_safe()` only if the doc doesn't already exist or is stale (`_check_knowledge_exists`/`_knowledge_is_current`) — this is idempotent seeding, not a per-mission integration check.
