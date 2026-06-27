# Microsoft Enterprise Architecture Documentation — theFactory / HGR

**Document version:** 2026.06.26
**Last updated:** 2026-06-26
**Status:** Approved / Canonical  
**Audience:** Enterprise Architects, Technical Stakeholders, Lead Engineers, and Auditors  
**Security Classification:** Restricted — Internal Use Only

---

## Executive Summary

**theFactory** (Holy Grail Refinery - HGR) is a distributed, multi-agent software manufacturing platform designed to ingest natural-language mission specifications and compile fully tested, compliant source code outputs.

This document serves as the canonical **Microsoft Enterprise Standard Architecture Documentation** for theFactory. It structures the system into logical viewpoints using a hybrid C4 Model (System Context, Container, Component) and specific enterprise concerns (Data Architecture, Dynamic Runtime Sequence, Agent Topology, Security Boundaries, and Physical Infrastructure).

---

## Table of Contents

1. [C4 Level 1: System Context View](#1-c4-level-1-system-context-view)
2. [C4 Level 2: Container Architecture View](#2-c4-level-2-container-architecture-view)
3. [C4 Level 3: Component View (Orchestrator)](#3-c4-level-3-component-view-orchestrator)
4. [C4 Level 3: Component View (API Gateway)](#4-c4-level-3-component-view-api-gateway)
5. [C4 Level 3: Component View (Protocol Bus MCP)](#5-c4-level-3-component-view-protocol-bus-mcp)
6. [Dynamic Runtime Sequence View](#6-dynamic-runtime-sequence-view)
7. [Multi-Agent Hierarchy & Cognitive Routing](#7-multi-agent-hierarchy-cognitive-routing)
8. [Information & Data Plane Architecture](#8-information-data-plane-architecture)
9. [Security, Encryption & Trust Boundaries](#9-security-encryption-trust-boundaries)
10. [Deployment & Infrastructure Topology](#10-deployment-infrastructure-topology)

---

## 1. C4 Level 1: System Context View

### Viewpoint Description
Defines the high-level boundary of theFactory platform, mapping the external actors (Operators, API Clients, Identity Providers) and external backend services (LLM APIs, Datastores).

```mermaid
flowchart TB
    Operator["Operator\n(Uses Mission Control UI / CLI)"]
    APIClient["External API Client\n(Mutates/Queries Missions via REST)"]
    IdP["OIDC Identity Provider\n(Enables Operator Authentication)"]

    subgraph Platform["theFactory (System Boundary)"]
        MC["Mission Control UI\nNext.js :3100"]
        GW["API Gateway\nFastAPI :8100"]
        Orch["Orchestrator\nFastAPI :8101"]
        Bus["Protocol Bus MCP\nFastAPI :8102"]
        Workers["Pod Workers\nPod A / B / C / D"]
        Audit["Audit Worker\nVerification & Handoff"]
    end

    subgraph External["External Services & Datastores"]
        LLM["LLM Providers\nOpenAI / Anthropic / Gemini"]
        Postgres["PostgreSQL DB"]
        Redis["Redis Stream/Cache"]
        Qdrant["Qdrant Vector DB"]
    end

    Operator -->|Accesses UI| MC
    APIClient -->|REST API Calls| GW
    MC <-->|REST + SSE| GW
    GW -.->|Validates Tokens| IdP
    GW <-->|REST Proxy| Orch
    Orch <-->|Redis Streams / RPC| Bus
    Bus <-->|Choreographed Events| Workers
    Workers -->|Indexes Knowledge| Qdrant
    Workers -->|Queries LLM API| LLM
    Orch -->|Queries LLM API| LLM
    Orch <-->|Saves State| Postgres
    Orch <-->|Deduplication/Locking| Redis
    Audit -->|Validates Evidence| Orch
```

### Components
- **Operator**: Interacts with the platform via Next.js web application or Electron desktop client.
- **External API Client**: Performs automated mission creation and queries status programmatically.
- **LLM Providers**: Generative AI backends used to evaluate, reason, and write code.

*Standalone Source File: [01_system_context.mermaid](01_system_context.mermaid)*

---

## 2. C4 Level 2: Container Architecture View

### Viewpoint Description
Details the internal container and microservices organization of theFactory. Outlines host port maps, communication protocols, and all seven database storage nodes.

```mermaid
flowchart TB
    Operator["Operator\n(Browser / Desktop Shell)"]
    APIClient["API Client\n(REST API Calls)"]

    subgraph EntryZone["Entry & Operator Surfaces"]
        MC["Mission Control UI\nNext.js :3100"]
        GW["API Gateway\nFastAPI :8100"]
        Dash["Dashboard\nFastAPI :8180"]
    end

    subgraph CoreServices["Core Control Plane"]
        Orch["Orchestrator\nFastAPI :8101"]
        Bus["Protocol Bus MCP\nFastAPI :8102"]
    end

    subgraph ExecutionZone["Execution Plane"]
        PodA["Pod A Worker\n(Dynamic languages)"]
        PodB["Pod B Worker\n(Systems languages)"]
        PodC["Pod C Worker\n(Enterprise languages)"]
        PodD["Pod D Worker\n(Mathematical languages)"]
        Audit["Audit Worker\n(Attestation & Handoff)"]
    end

    subgraph StateZone["State, Knowledge & Observability"]
        Postgres[(PostgreSQL\nState & Metrics)]
        RedisStreams[(Redis Streams\nEvent Queue)]
        Qdrant[(Qdrant\nVector Knowledge)]
        Neo4j[(Neo4j\nConcept Graph)]
        Minio[(MinIO / S3\nObject Storage)]
        Milvus[(Milvus\nAlternative Vector)]
        Jaeger[(Jaeger\nDistributed Traces)]
    end

    Operator -->|HTTP / IPC| MC
    Operator -->|HTTP| Dash
    APIClient -->|REST / HTTPS| GW
    MC <-->|REST + SSE| GW
    GW <-->|REST Proxy| Orch
    GW -.->|Audit Logs| Postgres
    Orch <-->|Durable Checkpointing| Postgres
    Orch <-->|SIGMA Bus| RedisStreams
    Orch <-->|Embeddings Query| Qdrant
    Orch -.->|Graph Linkage| Neo4j
    Orch -.->|Large Bundle Offload| Minio
    Orch -.->|Milvus Adapter| Milvus

    Bus <-->|Stream Sub/Pub| RedisStreams
    Bus -->|Validate Envelopes| RedisStreams
    PodA <-->|Subscribe / Publish| RedisStreams
    PodB <-->|Subscribe / Publish| RedisStreams
    PodC <-->|Subscribe / Publish| RedisStreams
    PodD <-->|Subscribe / Publish| RedisStreams
    Audit <-->|Subscribe / Publish| RedisStreams

    EntryZone & CoreServices & ExecutionZone -.->|Trace Export| Jaeger
```

### Communications & Storage Matrix
- **REST APIs**: Used for Control Plane configuration and intake operations.
- **Redis Streams**: The primary protocol bus connecting execution workers with the orchestrator.
- **Distributed Databases**: PostgreSQL holds mission relational states; Qdrant holds vectorized knowledge; Neo4j stores abstract syntax tree (AST) dependency concept maps.

*Standalone Source File: [02_container_architecture.mermaid](02_container_architecture.mermaid)*

---

## 3. C4 Level 3: Component View (Orchestrator)

### Viewpoint Description
A component breakdown of the central `orchestrator` service, highlighting the StateGraph runtime, delegation helpers, safety envelopes, and the storage facade.

```mermaid
flowchart TB
    GW["API Gateway\n(REST Calls)"]
    Bus["Protocol Bus\n(Redis Streams)"]

    subgraph Orchestrator["Orchestrator Component Boundary"]
        API["API Layer / Routes\n(FastAPI Controllers)"]
        Runtime["Runtime Engine\n(lifecycle_interface.py)"]
        FlowV2["Mission Flow v2 Engine\n(mission_flow_v2.py)"]
        Registry["Prompt Registry\n(prompt_registry.py)"]
        Safety["LLM Safety Envelope\n(llm_safety.py)"]
        Delegator["LLM Delegation Engine\n(llm_delegation.py)"]
        Cost["LLM Cost Ledger\n(llm_cost_ledger.py)"]
        RQCA["RQCA / TestData Agent\n(testdata_agent.py / rqca_agent.py)"]
        Storage["Storage Façade\n(storage.py & storage_*.py)"]
    end

    Postgres[(PostgreSQL)]
    Qdrant[(Qdrant)]
    Redis[(Redis)]

    GW -->|REST Requests| API
    API -->|Triggers Transitions| Runtime
    Runtime -->|Instantiates Engine| FlowV2
    FlowV2 -->|Loads Prompts| Registry
    FlowV2 -->|Evaluates Tests| RQCA
    FlowV2 -->|Queries/Updates State| Storage
    FlowV2 -->|Invokes Agents| Delegator
    Delegator -->|Filters Prompts/Responses| Safety
    Delegator -->|Logs Usage & Costs| Cost
    Storage -->|SQL Queries| Postgres
    Storage -->|Vector Indexing| Qdrant
    Cost -->|Persists Cost Metrics| Postgres
    Runtime <-->|Pub/Sub Event Bus| Bus
    RQCA -->|Test Manifest Caching| Redis
```

*Standalone Source File: [03_component_orchestrator.mermaid](03_component_orchestrator.mermaid)*

---

## 4. C4 Level 3: Component View (API Gateway)

### Viewpoint Description
Decomposes the public gateway, mapping the OAuth/OIDC/API-Key authenticator, sliding window rate limiter, and real-time Server-Sent Events (SSE) state streaming controller.

```mermaid
flowchart TB
    Operator["Operator / MC UI"]
    Client["External API Client"]

    subgraph Gateway["API Gateway Component Boundary"]
        Entry["ASGI Server\n(Uvicorn / FastAPI)"]
        Auth["Auth Manager\n(Bearer / API-Key / OIDC)"]
        Limiter["Rate Limiter\n(Sliding Window)"]
        Idemp["Idempotency Filter\n(SHA-256 Validation)"]
        Stream["SSE Stream Controller\n(v1/stream/state)"]
        Proxy["REST Proxy Router\n(/v1/operations/*)"]
    end

    Redis[(Redis Cache & Lock)]
    Orch["Orchestrator\nFastAPI :8101"]

    Operator & Client -->|Requests| Entry
    Entry -->|Validates Keys/Tokens| Auth
    Auth -->|Check Rate Limits| Limiter
    Limiter -->|Query Window| Redis
    Entry -->|Inspect IDEMPOTENCY-KEY| Idemp
    Idemp -->|Check/Set Lock| Redis
    Entry -->|Live Subscription| Stream
    Stream <-->|Polls Health & Events| Redis
    Entry -->|Route Ops| Proxy
    Proxy -->|Forward Calls| Orch
```

*Standalone Source File: [04_component_api_gateway.mermaid](04_component_api_gateway.mermaid)*

---

## 5. C4 Level 3: Component View (Protocol Bus MCP)

### Viewpoint Description
Highlights the routing rules, schema verification logic, and backpressure/replay mitigation components within the Protocol Bus microservice.

```mermaid
flowchart TB
    Orch["Orchestrator"]
    Workers["Pod Workers"]

    subgraph Bus["Protocol Bus MCP Component Boundary"]
        Entry["ASGI Server\n(FastAPI :8102)"]
        Router["6-Protocol Router\n(α, β, δ, σ, ω, ρ)"]
        Validator["Schema Validator\n(jsonschema.validate)"]
        Dedup["Replay & Dedup Filter\n(Correlation-ID Check)"]
        Backpressure["Backpressure Controller\n(Fail-Closed Check)"]
    end

    RedisStreams[(Redis Streams\nalpha | beta | delta | sigma | omega | rho)]
    RedisDedup[(Redis Cache\nduplicates | locks)]

    Orch & Workers -->|Publish Events| Entry
    Entry -->|Check Correlation-ID| Dedup
    Dedup -->|Lookup Key| RedisDedup
    Dedup -->|Check Load| Backpressure
    Backpressure -->|Query Stream Lengths| RedisStreams
    Entry -->|Validate Envelope Schema| Validator
    Validator -->|Parse Event Protocol| Router
    Router -->|Push to Stream| RedisStreams
```

*Standalone Source File: [05_component_protocol_bus.mermaid](05_component_protocol_bus.mermaid)*

---

## 6. Dynamic Runtime Sequence View

### Viewpoint Description
Illustrates the transaction and message flow from initial natural-language mission submission through agent extraction, verification gating, code generation, and delivery.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant MC as Mission Control UI
    participant GW as API Gateway (:8100)
    participant Orch as Orchestrator (:8101)
    participant Bus as Protocol Bus (:8102)
    participant Workers as Pod Workers
    participant Audit as Audit Worker
    participant Postgres as PostgreSQL DB

    Operator->>MC: Trigger new mission
    MC->>GW: POST /v1/missions (idempotent request)
    GW->>Orch: create_mission()
    Orch->>Postgres: Insert mission state (PM_INTAKE)
    Orch-->>GW: mission_id
    GW-->>MC: mission created

    rect rgb(20, 20, 30)
        note right of Orch: Smelt Cycle Begins (MissionFlow v2)
        Orch->>Bus: Publish Alpha Directive (α)
        Bus->>Workers: Dispatch Intake task
        Workers->>Orch: Return PM Charter (PM_INTAKE -> QUEUED)
    end

    rect rgb(25, 25, 40)
        note right of Orch: Core Execution (SMELT & FUSION)
        Orch->>Bus: Publish Beta Directive (β)
        Bus->>Workers: Dispatch extraction tasks
        Workers->>Workers: Extract LogicNodes (AST + Regex)
        Workers->>Orch: Return LogicNodes (Sigma Knowledge σ)
        Orch->>Postgres: Upsert LogicNodes
        Orch->>Orch: Merge to master logic stream
    end

    rect rgb(30, 20, 20)
        note right of Orch: Gating, Verification, Delivery
        Orch->>Bus: Publish Delta Directive (δ)
        Bus->>Audit: Dispatch verification task
        Audit->>Orch: GET /internal/review-approvals
        Orch-->>Audit: return review data
        Audit->>Audit: Verify signatures & equivalence
        Audit->>Orch: POST verification_report (VERIFIED)
        Orch->>Orch: Package build artifact with ECDSA signature
        Orch->>Postgres: Mark mission state (COMPLETE)
        Orch->>MC: SSE event state transition (COMPLETE)
    end
    
    Operator->>MC: View generated code & cost summary
```

*Standalone Source File: [06_mission_intake_lifecycle_sequence.mermaid](06_mission_intake_lifecycle_sequence.mermaid)*

---

## 7. Multi-Agent Hierarchy & Cognitive Routing

### Viewpoint Description
Details the command structure, support agents, specialist language worker pods, and system slot agents (AGENT-01 through AGENT-41) that collaborate to smelt the code.

```mermaid
flowchart TD
    PM["AGENT-01-PM\nProgram manager / mission intake"]
    CEO["AGENT-02-CEO\nCross-pod orchestration"]

    subgraph SupportRing["Support Ring"]
        Broker["AGENT-03-BROKER"]
        Accountant["AGENT-04-ACCOUNTANT"]
        Sec["AGENT-05-SECURITY"]
        IS["AGENT-06-IS"]
        VC["AGENT-07-VC"]
        Compliance["AGENT-08-COMPLIANCE"]
        HW["AGENT-09-HW"]
        Tester["AGENT-10-TESTER"]
        Deploy["AGENT-11-DEPLOY"]
        Depabs["AGENT-39-DEPABS"]
        Testdata["AGENT-40-TESTDATA"]
        Rqca["AGENT-41-RQCA"]
    end

    subgraph PodA["Pod A — Dynamic"]
        A_Mgr["AGENT-12-PODA-MGR"]
        A_Aud["AGENT-13-PODA-AUDIT"]
        A_Py["AGENT-14-PYTHON"]
        A_JS["AGENT-15-JAVASCRIPT"]
        A_Ruby["AGENT-16-RUBY"]
        A_PHP["AGENT-17-PHP"]
    end

    subgraph PodB["Pod B — Systems"]
        B_Mgr["AGENT-18-PODB-MGR"]
        B_Aud["AGENT-19-PODB-AUDIT"]
        B_C["AGENT-20-C"]
        B_Cpp["AGENT-21-CPP"]
        B_Rust["AGENT-22-RUST"]
        B_Zig["AGENT-23-ZIG"]
        B_Go["AGENT-36-GO"]
    end

    subgraph PodC["Pod C — Enterprise"]
        C_Mgr["AGENT-24-PODC-MGR"]
        C_Aud["AGENT-25-PODC-AUDIT"]
        C_Java["AGENT-26-JAVA"]
        C_Cs["AGENT-27-CSHARP"]
        C_Scala["AGENT-28-SCALA"]
        C_Kotlin["AGENT-29-KOTLIN"]
    end

    subgraph PodD["Pod D — Mathematical"]
        D_Mgr["AGENT-30-PODD-MGR"]
        D_Aud["AGENT-31-PODD-AUDIT"]
        D_Matlab["AGENT-32-MATLAB"]
        D_R["AGENT-33-R"]
        D_Julia["AGENT-34-JULIA"]
        D_Math["AGENT-35-MATHEMATICA"]
        D_Hask["AGENT-37-HASKELL"]
        D_Ocaml["AGENT-38-OCAML"]
    end

    PM -->|Normalizes missions| CEO
    SupportRing -. advisory / policy / QC .-> CEO
    CEO -->|Delegates work| A_Mgr & B_Mgr & C_Mgr & D_Mgr

    A_Mgr --> A_Aud
    A_Mgr --> A_Py & A_JS & A_Ruby & A_PHP

    B_Mgr --> B_Aud
    B_Mgr --> B_C & B_Cpp & B_Rust & B_Zig & B_Go

    C_Mgr --> C_Aud
    C_Mgr --> C_Java & C_Cs & C_Scala & C_Kotlin

    D_Mgr --> D_Aud
    D_Mgr --> D_Matlab & D_R & D_Julia & D_Math & D_Hask & D_Ocaml
```

*Standalone Source File: [07_agent_hierarchy_delegation.mermaid](07_agent_hierarchy_delegation.mermaid)*

---

## 8. Information & Data Plane Architecture

### Viewpoint Description
Details database queries, caching layers, and vector synchronization pipelines, demonstrating how relational structures, knowledge graphs, and S3-offloaded storage backends interact.

```mermaid
flowchart TD
    Orch["Orchestrator"]
    Workers["Pod Workers"]
    Audit["Audit Worker"]

    subgraph RelationalStore["Relational / Checkpoint Layer"]
        Postgres[(PostgreSQL)]
    end

    subgraph MessagingStream["Pub/Sub Event Broker"]
        RedisStreams[(Redis Streams)]
    end

    subgraph VectorKnowledge["Semantic Knowledge Base"]
        Qdrant[(Qdrant Vector DB)]
        Milvus[(Milvus Vector DB)]
    end

    subgraph ConceptGraph["Dependency Graph"]
        Neo4j[(Neo4j Graph DB)]
    end

    subgraph ObjectStorage["Large Payload Storage"]
        Minio[(MinIO / S3)]
    end

    Orch -->|1. Write State & Checkpoints| Postgres
    Orch -->|2. Publish α/β/δ Directives| RedisStreams
    RedisStreams -->|3. Consume Directives| Workers
    Workers -->|4. Query/Cache Templates| RedisStreams
    Workers -->|5. Extract & Write LogicNodes| Qdrant
    Workers -.->|6. Sink Concept Links| Neo4j
    Workers -->|7. Publish σ Knowledge Event| RedisStreams
    RedisStreams -->|8. Fetch σ Payload| Orch
    Orch -.->|9. Map LogicNode Dependencies| Neo4j
    Orch -.->|10. Backup Source Bundle| Minio
    Orch -->|11. Query Reference Context| Qdrant
    Orch -.->|12. Sync Milvus Indexes| Milvus
    Orch -->|13. Publish δ Audit Event| RedisStreams
    RedisStreams -->|14. Consume Audit Event| Audit
    Audit -->|15. Validate Attestation| Postgres
    Audit -->|16. POST Complete Verdict| Orch
```

*Standalone Source File: [08_data_information_flow.mermaid](08_data_information_flow.mermaid)*

---

## 9. Security, Encryption & Trust Boundaries

### Viewpoint Description
Highlights the encryption zones, Mutual TLS links, DPAPI-protected private signing key store (A2 compliance), and output sanitation filters.

```mermaid
flowchart TB
    Operator["Operator\n(Browser)"]
    APIClient["API Client"]

    subgraph TrustZone_Public["Public untrusted boundary (HTTP/HTTPS)"]
        MC["Mission Control Server"]
        GW["API Gateway"]
    end

    subgraph TrustZone_Internal["Internal secure boundary (Mutual TLS / Service Token)"]
        Orch["Orchestrator\n(FastAPI)"]
        Bus["Protocol Bus\n(MCP :8102)"]
        Workers["Pod Workers\n(Python/JS/Java/Mathematical)"]
        Audit["Audit Worker"]
    end

    subgraph StateStore["Protected Datastores"]
        Postgres[(PostgreSQL\nTLS Encrypted)]
        Redis[(Redis\nTLS Encrypted)]
    end

    subgraph HostKeystore["Host Security Layer"]
        DPAPI["Windows DPAPI\n(Keystore A2)"]
        PEM["PEM Secrets fallback\n(Docker secret mount)"]
    end

    Operator -->|1. Signed operator session cookie| MC
    APIClient -->|2. x-api-key or OIDC JWT| GW
    MC -->|3. INTERNAL_SERVICE_API_KEY| GW
    GW -->|4. Forward auth request| Orch
    Orch -->|5. Query active sessions (TLS)| Redis
    Orch -->|6. Load credentials (TLS)| Postgres

    Orch -->|7. Access Protected Key| DPAPI
    Orch -->|7. Access Protected Key| PEM

    Orch <-->|8. Signed Events (TLS)| Bus
    Bus <-->|9. Signed Payload Event (TLS)| Workers
    Bus <-->|10. Evidence Verification (TLS)| Audit

    subgraph LLMSafety["LLM Safety Envelope"]
        Safety["llm_safety.py\n(Secret Sanitizer & Prompt Injection Block)"]
    end

    Orch & Workers -->|11. Filter outbound prompt| Safety
    Safety -->|12. Request codegen| LLM["LLM Provider APIs\n(HTTPS)"]
```

*Standalone Source File: [09_security_trust_boundaries.mermaid](09_security_trust_boundaries.mermaid)*

---

## 10. Deployment & Infrastructure Topology

### Viewpoint Description
Maps physical container deployment layouts, environment configuration profiles, and isolation options (Base condensed, dedicated, and full-dedicated specialist modes).

```mermaid
flowchart TB
    Client["Operator / External Client"]

    subgraph Host["Physical / Host Server Environment"]
        subgraph Ports["Host Port Mappings"]
            Port3100["Port 3100: Mission Control"]
            Port8100["Port 8100: API Gateway"]
            Port8180["Port 8180: Dashboard"]
            Port5434["Port 5434: PgBouncer"]
            Port6380["Port 6380: Redis"]
        end

        subgraph DockerCompose["Docker Compose Stack"]
            subgraph BaseStack["Base Compose Profile (condensed)"]
                MC_Container["deploy-mission-control-1\n(Next.js Node WebApp)"]
                GW_Container["deploy-api-gateway-1\n(FastAPI Gateway)"]
                Orch_Container["deploy-orchestrator-1\n(FastAPI Orchestrator)"]
                Bus_Container["deploy-protocol-bus-mcp-1\n(FastAPI MCP Bus)"]
                PodWorkers_Container["deploy-pod-worker-1\n(Shared worker container for A/B/C/D)"]
                Audit_Container["deploy-audit-worker-1\n(Python Audit execution)"]
                Db["deploy-postgres-1\n(PostgreSQL Database)"]
                Cache["deploy-redis-1\n(Redis Streams & Cache)"]
            end

            subgraph DedicatedProfile["Dedicated Profile (dedicated-agents)"]
                PodA_Mgr["deploy-pod-a-manager-1"]
                PodB_Mgr["deploy-pod-b-manager-1"]
                PodC_Mgr["deploy-pod-c-manager-1"]
                PodD_Mgr["deploy-pod-d-manager-1"]
            end

            subgraph FullDedicatedProfile["Full Dedicated Profile (full-dedicated-agents)"]
                LangSpecialists["Isolated language specialist containers\n(One container per SpecialistAgent class)"]
            end
        end
    end

    Client -->|Browser| Port3100
    Client -->|REST API| Port8100
    Client -->|Stats| Port8180

    Port3100 --> MC_Container
    Port8100 --> GW_Container
    Port8180 --> BaseStack
    Port5434 --> Db
    Port6380 --> Cache

    GW_Container <--> Orch_Container
    Orch_Container <--> Bus_Container
    Bus_Container <--> PodWorkers_Container
    Bus_Container <--> Audit_Container

    Orch_Container -.->|Overlay control| PodA_Mgr & PodB_Mgr & PodC_Mgr & PodD_Mgr
    Orch_Container -.->|Overlay control| LangSpecialists
```

*Standalone Source File: [10_deployment_infrastructure.mermaid](10_deployment_infrastructure.mermaid)*
