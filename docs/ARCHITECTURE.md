# Architecture Snapshot

Last updated: 2026-03-02

## Runtime Topology

- API Gateway: mission intake boundary, idempotent request handling, rate limiting, external-facing API contracts.
- Orchestrator: mission lifecycle state machine, pod assignment logic, agent telemetry synthesis, operations snapshots.
- Dashboard: lightweight operational status surface.
- Worker services:
  - pod A worker
  - pod B worker
  - pod C worker
  - pod D worker
  - audit worker
- Mission Control: Next.js operator UI for mission and agent operations.
- Semantic/event plane: Redis Streams.
- Persistence plane: PostgreSQL (primary), Qdrant (reserved), Neo4j/object-storage (planned optional).
- Observability plane: Prometheus, Alertmanager, Grafana, Loki, Promtail.

## Control Plane Contracts

Primary contract artifacts:

- `schemas/event.envelope.schema.json`: semantic-bus envelope contract.
- `schemas/logicnode.schema.json`: language-agnostic LogicNode contract.
- `schemas/rir.module.schema.json`: Refined-IR module contract.
- `schemas/rir.fn.schema.json`: Refined-IR function contract.
- `protocol/topics.yaml`: protocol topic catalog.

## Mission Lifecycle Path

1. Mission intake at Gateway (`POST /v1/missions`).
2. Dedupe/idempotency checks with Redis-backed key handling.
3. Orchestrator persistence and transition into lifecycle states.
4. Streamed state events and pod routing.
5. Pod workers process compatible language/paradigm workloads.
6. Audit worker and orchestration integration update verification and completion state.
7. Operations APIs expose mission/agent telemetry for Mission Control.

## 35-Agent Architecture

The orchestrator registry defines 35 agents across:

- Interface tier
- Executive tier
- Support ring
- Pod A/B/C/D sub-manager, audit, specialist roles

Each agent has two parallel representations in runtime snapshots:

- **Operational profile**:
  - runtime state
  - queue depth / workload
  - heartbeat source/age
  - active mission assignment
- **Persona profile**:
  - 8-part role/persona structure
  - standards alignment metadata
  - evidence-source links for governance traceability

Persona profile implementation entry point:

- `services/orchestrator/orchestrator/agent_personas.py`

## Operations Endpoints for Agent Topology

- `GET /internal/operations/agents`
  - runtime telemetry for all 35 agents
  - includes `persona_profile`
- `GET /internal/operations/agent-integrations`
  - protocol and data-system assignments
  - per-agent LLM recommendations
  - includes `persona_profile`
  - includes persona metadata fields:
    - `persona_profile_framework`
    - `persona_profile_sections`
    - `persona_profile_extensions`
    - `standards_evidence_last_verified`

Gateway mirrors these on:

- `GET /v1/operations/agents`
- `GET /v1/operations/agent-integrations`

## Production Baseline Controls (Implemented)

1. Health/readiness/metrics contracts on gateway and orchestrator.
2. Mission idempotency and deterministic replay.
3. API rate-limiting and hardened security headers.
4. Role-based key enforcement on mutation/internal paths.
5. CI + audit scripts for baseline security and quality gates.
6. Non-root container runtime users.
7. Operations scripts for predeploy, backup, restore, DR drill, perf smoke, debug sweep.

## Architecture Expansion Tracks

1. Enforce release signing and attestations end-to-end in promotion pipeline.
2. Add distributed tracing and alert routing automation.
3. Activate reserved vector knowledge path (Qdrant) in production workflows.
4. Add optional Neo4j/object-storage adapters behind feature flags for advanced use cases.
