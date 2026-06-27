# Architecture Diagrams

Document version: 2026.06.26
Last updated: 2026-06-26
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

This document contains the canonical diagrams for theFactory. It follows the diagram set defined in
[`DIAGRAM_STANDARDS.md`](DIAGRAM_STANDARDS.md) and is intended to stay aligned with the runtime,
compose profiles, and agent registry in the codebase.

For the detailed runtime, identity, approval, artifact, and telemetry flows, see
[`ARCHITECTURE_DATA_FLOWS.md`](ARCHITECTURE_DATA_FLOWS.md).

## Diagram Catalog

| Diagram | Purpose |
|---------|---------|
| System context view | Shows external actors, entrypoints, and major dependencies |
| Container view | Shows the main runtime services and relationships inside the platform |
| Mission lifecycle state view | Shows canonical mission-state progression and the optional v2 path |
| Mission runtime sequence | Shows the end-to-end mission execution path |
| Multi-agent topology view | Shows the 41-agent hierarchy and delegation structure |
| Data and knowledge plane view | Shows streams, persistence, vector stores, graph store, and artifacts |
| Deployment profile view | Shows the base stack and overlay-based runtime modes |
| Security and trust-boundary view | Shows auth boundaries, service keys, and TLS-protected internal paths |

## System Context View

```mermaid
flowchart TB
    Operator["Operator"]
    APIClient["External API Client"]
    IdP["OIDC Identity Provider\noptional for hybrid / oidc"]

    subgraph Platform["theFactory"]
        MissionControl["Mission Control UI\nNext.js 16 :3100"]
        Dashboard["Dashboard\nFastAPI :8180"]
        Gateway["API Gateway\nFastAPI :8100"]
        Orchestrator["Orchestrator\nFastAPI :8101"]
        ProtocolBus["Protocol Bus MCP\nFastAPI :8102"]
        PodWorkers["Pod Workers\npodA / podB / podC / podD"]
        AuditWorker["Audit Worker"]
        AgentRuntime["Agent Runtime\nfull-dedicated-agents profile"]
        Redis["Redis :6380"]
        Postgres["PostgreSQL :5433"]
        Qdrant["Qdrant :6334"]
        Milvus["Milvus :19530\noptional"]
        Neo4j["Neo4j\noptional"]
        MinIO["MinIO / S3\noptional"]
    end

    Operator --> MissionControl
    Operator --> Dashboard
    APIClient --> Gateway
    MissionControl <--> Gateway
    Gateway -. "JWT validation when enabled" .-> IdP
    Gateway <--> Orchestrator
    ProtocolBus <--> Redis
    PodWorkers <--> Redis
    AuditWorker <--> Redis
    AgentRuntime <--> Redis
    Orchestrator <--> Redis
    Orchestrator <--> Postgres
    Orchestrator <--> Qdrant
    Orchestrator -. "feature-flagged" .-> Milvus
    Orchestrator -. "feature-flagged" .-> Neo4j
    Orchestrator -. "feature-flagged" .-> MinIO
    PodWorkers <--> Orchestrator
    AuditWorker --> Orchestrator
    AgentRuntime --> Orchestrator
```

## Container View

```mermaid
flowchart LR
    subgraph Entry["Entry and Operator Surfaces"]
        MC["Mission Control\nNext.js :3100"]
        GW["API Gateway\nFastAPI :8100"]
        Dash["Dashboard\nFastAPI :8180"]
    end

    subgraph Core["Core Control Plane"]
        Orch["Orchestrator\nFastAPI :8101"]
        Bus["Protocol Bus MCP\nFastAPI :8102"]
    end

    subgraph Execution["Execution Plane"]
        PodA["pod-worker podA"]
        PodB["pod-worker podB"]
        PodC["pod-worker podC"]
        PodD["pod-worker podD"]
        Audit["audit-worker"]
        DedicatedMgr["Dedicated pod-manager workers\noptional profile"]
        AgentRT["agent-runtime containers\nfull dedicated profile"]
    end

    subgraph State["State and Knowledge"]
        Redis["Redis Streams"]
        PG["PostgreSQL"]
        Qdrant["Qdrant"]
        Milvus["Milvus optional"]
        Neo4j["Neo4j optional"]
        MinIO["MinIO / S3 optional"]
    end

    subgraph Observability["Observability"]
        Prom["Prometheus"]
        Graf["Grafana"]
        Loki["Loki"]
        Alert["Alertmanager"]
        Jaeger["Jaeger"]
    end

    MC --> GW
    Dash --> GW
    GW --> Orch
    Orch <--> Redis
    Orch <--> PG
    Orch <--> Qdrant
    Orch -.-> Milvus
    Orch -.-> Neo4j
    Orch -.-> MinIO
    Bus <--> Redis
    Orch --> Redis
    PodA <--> Redis
    PodB <--> Redis
    PodC <--> Redis
    PodD <--> Redis
    Audit <--> Redis
    DedicatedMgr <--> Redis
    AgentRT <--> Redis
    PodA --> Orch
    PodB --> Orch
    PodC --> Orch
    PodD --> Orch
    Audit --> Orch
    DedicatedMgr --> Orch
    AgentRT --> Orch
    Prom --> GW
    Prom --> Orch
    Prom --> Bus
    Prom --> Audit
    Prom --> Dash
    Prom --> AgentRT
    GW --> Jaeger
    Orch --> Jaeger
    Bus --> Jaeger
    Audit --> Jaeger
    AgentRT --> Jaeger
    Graf --> Prom
    Graf --> Loki
    Alert --> Prom
```

## Mission Lifecycle State View

```mermaid
stateDiagram-v2
    [*] --> QUEUED: MISSION_INTAKE
    QUEUED --> RUNNING: MISSION_QUEUED / MISSION_GATING
    RUNNING --> VERIFIED: MISSION_FUSION and audit handoff
    VERIFIED --> COMPLETE: MISSION_COMPLETE
    RUNNING --> FAILED: execution or validation failure
    VERIFIED --> FAILED: integrity failure or completion block

    state RUNNING {
        [*] --> PM_INTAKE
        PM_INTAKE --> CEO_DELEGATED
        CEO_DELEGATED --> POD_MANAGER_ASSIGNED
        POD_MANAGER_ASSIGNED --> SPECIALIST_ASSIGNED
        SPECIALIST_ASSIGNED --> EXECUTING
        SPECIALIST_ASSIGNED --> SPECIALIST_PLANNED: when MISSION_FLOW_V2_ENABLED=true
        SPECIALIST_PLANNED --> EXECUTING
        EXECUTING --> FUSION
    }
```

## Mission Runtime Sequence

```mermaid
sequenceDiagram
    actor User
    participant MC as Mission Control
    participant GW as API Gateway
    participant Orch as Orchestrator
    participant PG as PostgreSQL
    participant Redis as Redis Streams
    participant Pod as Pod Worker
    participant Audit as Audit Worker

    User->>MC: Submit mission
    MC->>GW: POST /v1/missions
    GW->>Orch: Validate, dedupe, forward
    Orch->>PG: Persist mission and initial state
    Orch->>Redis: Publish intake and state events
    alt Default Mission Flow v2 path (MISSION_FLOW_V2_ENABLED=true)
        Orch->>Redis: Emit PM / CEO / pod-manager / specialist-planned events
    else Legacy compatibility path when v2 is disabled
        Orch->>Redis: Emit canonical v1.1 lifecycle events
    end
    Orch->>Redis: Queue work on missions.pod.A/B/C/D
    Pod->>Orch: POST /internal/pod-assignment
    Pod->>Orch: POST /internal/logicnodes
    Pod->>Orch: POST /internal/knowledge
    Pod->>Redis: Publish progress and heartbeats
    Audit->>Orch: POST /internal/audit-reports
    Orch->>PG: Transition VERIFIED to COMPLETE
    GW-->>MC: SSE via /v1/stream/state
    MC-->>User: Timeline, chain trace, artifacts
```

## Multi-Agent Topology View

```mermaid
flowchart TB
    PM["AGENT-01-PM\nMission intake and normalization"]
    CEO["AGENT-02-CEO\nCross-pod orchestration"]
    SupportHub["Support Ring\nAGENT-03 through AGENT-11"]

    subgraph Support["Support Ring (9)"]
        Broker["03 Broker"]
        Accountant["04 Accountant"]
        Security["05 Security"]
        IS["06 IS"]
        VC["07 VC"]
        Compliance["08 Compliance"]
        HW["09 HW"]
        Tester["10 Tester"]
        Deploy["11 Deploy"]
    end

    subgraph PodA["Pod A Dynamic (6)"]
        A12["12 PodA Manager"]
        A13["13 PodA Audit"]
        A14["14 Python"]
        A15["15 JavaScript"]
        A16["16 Ruby"]
        A17["17 PHP"]
    end

    subgraph PodB["Pod B Systems (7)"]
        B18["18 PodB Manager"]
        B19["19 PodB Audit"]
        B20["20 C"]
        B21["21 C++"]
        B22["22 Rust"]
        B23["23 Zig"]
        B36["AGENT-36-GO\nGo"]
    end

    subgraph PodC["Pod C Enterprise (6)"]
        C24["24 PodC Manager"]
        C25["25 PodC Audit"]
        C26["26 Java"]
        C27["27 C#"]
        C28["28 Scala"]
        C29["29 Kotlin"]
    end

    subgraph PodD["Pod D Mathematical (8)"]
        D30["30 PodD Manager"]
        D31["31 PodD Audit"]
        D32["32 MATLAB"]
        D33["33 R"]
        D34["34 Julia"]
        D35["35 Mathematica"]
        D37["AGENT-37-HASKELL\nHaskell"]
        D38["AGENT-38-OCAML\nOCaml"]
    end

    subgraph Quality["Support Capability Expansion (3)"]
        Q39["AGENT-39-DEPABS"]
        Q40["AGENT-40-TESTDATA"]
        Q41["AGENT-41-RQCA"]
    end

    PM --> CEO
    Broker --> SupportHub
    Accountant --> SupportHub
    Security --> SupportHub
    IS --> SupportHub
    VC --> SupportHub
    Compliance --> SupportHub
    HW --> SupportHub
    Tester --> SupportHub
    Deploy --> SupportHub
    SupportHub -. advisory, policy, audit, delivery .-> CEO

    CEO --> A12
    CEO --> B18
    CEO --> C24
    CEO --> D30

    A12 --> A13
    A12 --> A14
    A12 --> A15
    A12 --> A16
    A12 --> A17

    B18 --> B19
    B18 --> B20
    B18 --> B21
    B18 --> B22
    B18 --> B23
    B18 --> B36

    C24 --> C25
    C24 --> C26
    C24 --> C27
    C24 --> C28
    C24 --> C29

    D30 --> D31
    D30 --> D32
    D30 --> D33
    D30 --> D34
    D30 --> D35
    D30 --> D37
    D30 --> D38

    CEO -. support work .-> Q39
    CEO -. test data .-> Q40
    CEO -. runtime QC .-> Q41
```

## Data and Knowledge Plane View

```mermaid
flowchart LR
    GW["API Gateway"]
    Orch["Orchestrator"]
    Bus["Protocol Bus MCP"]
    Pod["Pod Workers"]
    Audit["Audit Worker"]
    AgentRT["Agent Runtime"]

    Redis["Redis Streams\nmissions.intake\nmissions.state\nmissions.pod.*\nmissions.audit\nagents.heartbeats"]
    PG["PostgreSQL\nmissions, events, assignments,\nlogicnodes, audits, traceability"]
    Qdrant["Qdrant\nactive knowledge retrieval"]
    Milvus["Milvus optional\nextended retrieval path"]
    Neo4j["Neo4j optional\nrelationship graph"]
    MinIO["MinIO / S3 optional\nimmutable audit artifacts"]

    GW --> Orch
    Bus <--> Redis
    Orch <--> Redis
    Orch <--> PG
    Orch <--> Qdrant
    Orch -.-> Milvus
    Orch -.-> Neo4j
    Orch -.-> MinIO
    Pod <--> Redis
    Pod --> Orch
    Audit <--> Redis
    Audit --> Orch
    AgentRT <--> Redis
    AgentRT --> Orch
```

## Deployment Profile View

```mermaid
flowchart TB
    Base["Base runtime\napi-gateway\norchestrator\nprotocol-bus-mcp\npod-worker x4\naudit-worker\ndashboard\nmission-control\nredis\npostgres\nqdrant\njaeger\nMilvus\nNeo4j\nMinIO"]
    Monitoring["Monitoring stack\nPrometheus\nGrafana\nLoki\nPromtail\nAlertmanager"]
    Prod["Production overlay\ndeploy/docker-compose.prod.yaml\nstrict worker key mode\nTLS verification settings"]
    Dedicated["dedicated-agents profile\ndedicated pod-manager workers"]
    FullDedicated["full-dedicated-agents overlay\nagent-runtime containers\ndedicated specialist and capability workers\nMISSION_FLOW_V2_ENABLED=true"]

    Base --> Monitoring
    Base --> Prod
    Base --> Dedicated
    Base --> FullDedicated
    Dedicated --> FullDedicated
```

## Security and Trust-Boundary View

```mermaid
flowchart LR
    subgraph External["External boundary"]
        Operator["Operator"]
        APIClient["API Client"]
        IdP["OIDC Identity Provider"]
    end

    subgraph Public["Public entrypoint"]
        MC["Mission Control"]
        GW["API Gateway\nAUTH_MODE api_key / hybrid / oidc"]
    end

    subgraph Internal["Internal service network"]
        Orch["Orchestrator"]
        Workers["pod-worker / audit-worker / agent-runtime"]
        Redis["Redis TLS\nssl_cert_reqs=required"]
        PG["PostgreSQL TLS\nsslmode=verify-full"]
    end

    Operator --> MC
    APIClient --> GW
    MC --> GW
    GW -. bearer validation .-> IdP
    GW -. INTERNAL_SERVICE_API_KEY .-> Orch
    Workers -. agent-scoped service key .-> Orch
    Orch <--> Redis
    Orch <--> PG
    Workers <--> Redis
```

## Maintenance Notes

- Keep these diagrams aligned with `deploy/docker-compose*.yaml`, `services/orchestrator`, and the
  canonical docs in `README.md`, `ARCHITECTURE.md`, `OPERATIONS_RUNBOOK.md`, and `IMPLEMENTATION_STATUS.md`.
- Treat `MISSION_FLOW_V2_ENABLED=true` as the default runtime baseline unless the
  runtime defaults change in code.
- Update the multi-agent topology view whenever `services/orchestrator/orchestrator/agent_registry.py`
  changes.


