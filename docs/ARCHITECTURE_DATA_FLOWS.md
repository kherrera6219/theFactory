# Architecture Data Flows

Document version: 2026.03.29  
Last updated: 2026-03-29  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

This document captures the critical application, identity, and data flows for theFactory. It complements [ARCHITECTURE.md](ARCHITECTURE.md) and [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) by focusing on runtime movement of requests, credentials, artifacts, telemetry, and persistent state.

## Flow Catalog

- Mission intake and lifecycle flow
- Review approval and launch flow
- Build artifact packaging and retrieval flow
- Identity and access flow
- Observability and telemetry flow

## Mission Intake and Lifecycle Flow

```mermaid
flowchart LR
    Operator["Operator / API Client"]
    MissionControl["Mission Control"]
    Gateway["API Gateway :8100"]
    Orchestrator["Orchestrator :8101"]
    Redis["Redis Streams"]
    PodWorkers["Pod Workers"]
    AuditWorker["Audit Worker"]
    Postgres["PostgreSQL"]
    Qdrant["Qdrant"]

    Operator --> MissionControl
    Operator --> Gateway
    MissionControl --> Gateway
    Gateway --> Orchestrator
    Gateway --> Redis
    Orchestrator --> Postgres
    Orchestrator --> Redis
    Redis --> PodWorkers
    PodWorkers --> Orchestrator
    PodWorkers --> Qdrant
    Redis --> AuditWorker
    AuditWorker --> Orchestrator
    Orchestrator --> Postgres
```

Key properties:

- The gateway owns public intake concerns such as auth, idempotency, rate limiting, and correlation IDs.
- The orchestrator owns mission state, agent routing, approval persistence, build-artifact persistence, and internal operations views.
- Redis Streams connect the orchestrator, pod workers, semantic bus, audit worker, and optional dedicated runtime containers.

## Review Approval and Mission Launch Flow

```mermaid
sequenceDiagram
    participant Operator
    participant MissionControl
    participant ReviewRoute as /api/review/approve
    participant Orchestrator
    participant Postgres
    participant Gateway

    Operator->>MissionControl: Approve builder or repo review
    MissionControl->>ReviewRoute: POST approval request
    ReviewRoute->>Orchestrator: POST /internal/review-approvals
    Orchestrator->>Postgres: upsert review_approvals row
    Orchestrator-->>ReviewRoute: approval_id + record_path
    ReviewRoute-->>MissionControl: durable approval record
    MissionControl->>Gateway: POST /v1/missions with approved bundle
    Gateway->>Orchestrator: create mission
```

Key properties:

- Review approvals are durable runtime records, not local filesystem receipts.
- Mission Control depends on `ORCHESTRATOR_INTERNAL_BASE_URL` and `INTERNAL_SERVICE_API_KEY` for the approval persistence step.
- Approved builder/repo bundles become part of mission metadata and drive later artifact packaging.

## Build Artifact Packaging and Retrieval Flow

```mermaid
sequenceDiagram
    participant Orchestrator
    participant Lifecycle as Mission Lifecycle
    participant BuildArtifacts as build_artifacts.py
    participant Postgres
    participant Gateway
    participant MissionControl

    Lifecycle->>BuildArtifacts: package source bundle at VERIFIED
    BuildArtifacts->>Postgres: upsert mission_build_artifacts row
    Lifecycle->>Orchestrator: gate COMPLETE on successful artifact
    Gateway->>Orchestrator: GET build-artifact list/detail
    Orchestrator-->>Gateway: artifact metadata + digest + manifest
    Gateway-->>MissionControl: public artifact response
```

Key properties:

- Source-bundle missions package a durable `source_bundle_package` artifact at `VERIFIED`.
- Completion for source-bundle missions requires both lifecycle success and a successful stored build artifact.
- Mission Control surfaces artifact status, digest, manifest, storage backend, and size.

## Identity and Access Flow

```mermaid
flowchart TB
    User["Operator / API Client"]
    IdP["OIDC Provider (optional)"]
    MissionControl["Mission Control"]
    Gateway["API Gateway"]
    Orchestrator["Orchestrator"]
    Workers["Workers / Internal services"]

    User -->|x-api-key or Bearer token| Gateway
    User --> MissionControl
    MissionControl -->|public API calls| Gateway
    Gateway -. hybrid/oidc validation .-> IdP
    MissionControl -->|INTERNAL_SERVICE_API_KEY| Orchestrator
    Workers -->|INTERNAL_SERVICE_API_KEY| Orchestrator
    Gateway -->|forward trusted internal call| Orchestrator
```

Key properties:

- Public mutations terminate at the gateway and are controlled by `AUTH_MODE`.
- Internal worker and Mission Control approval-persistence flows use `INTERNAL_SERVICE_API_KEY`.
- The gateway and orchestrator both accept `x-request-id` or `x-correlation-id` and echo `X-Correlation-Id`.

## Observability and Telemetry Flow

```mermaid
flowchart LR
    Services["Gateway / Orchestrator / Pod Workers / Audit / Semantic Bus / Agent Runtime"]
    Prometheus["Prometheus"]
    Loki["Loki / Promtail"]
    Jaeger["Jaeger OTLP"]
    Grafana["Grafana"]
    Alertmanager["Alertmanager"]

    Services --> Prometheus
    Services --> Loki
    Services --> Jaeger
    Prometheus --> Grafana
    Loki --> Grafana
    Jaeger --> Grafana
    Prometheus --> Alertmanager
```

Key properties:

- Metrics, logs, and traces are emitted across the control and execution planes.
- Correlation IDs provide a request-level bridge from gateway/operator actions into downstream traces and logs.
- Qualification and release evidence are stored under `docs/evidence/` rather than implied by prose-only documentation.
