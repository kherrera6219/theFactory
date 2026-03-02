# Agent Semantic Bus and Data Systems Plan

Date: 2026-03-02

## Scope

This document reconciles:

- Holygrail source documentation in `C:\software\Holygrail` (agent architecture, communication, data architecture, semantic bus, database setup, knowledge lake, and communication patterns).
- Current implementation in `C:\software\Holygrail\theFactory`.
- Current production standards from official vendor documentation for Redis, PostgreSQL, Neo4j, and object storage.

## Reconciled Architecture Baseline

Implemented in `theFactory` now:

- Redis stream/message backbone for mission and agent events.
- PostgreSQL as the primary mission, event, artifact, and telemetry state store.
- 35-agent orchestrator registry with live operations snapshots and heartbeat/state telemetry.

Declared/reserved/planned in current docs and code:

- Qdrant is reserved in current blueprint and intended to move into active knowledge retrieval path.
- Neo4j remains optional/planned for knowledge graph and relationship traversal use cases.
- Object storage remains planned for large immutable artifacts (binaries, audit evidence, large payload bundles).

## Phase 1 Completed in Repo

Implemented in this phase:

- Added a machine-readable per-agent integration registry:
  - `services/orchestrator/orchestrator/agent_integrations.py`
- Added operations endpoint:
  - `GET /internal/operations/agent-integrations`
- Added API Gateway route:
  - `GET /v1/operations/agent-integrations`
- Added regression coverage:
  - `tests/services/test_orchestrator_endpoints_extra.py`
  - `tests/services/test_production_foundations.py`
- Added per-agent LLM provider/model recommendations and thinking profiles:
  - `docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`

## Per-Agent Integration Matrix

Legend:

- Bus Role: semantic-bus direction and protocol ownership.
- Data Systems: currently expected internal systems for the agent (`redis`, `postgresql`, `qdrant` reserved, `neo4j` planned optional, `object_storage` planned).
- Canonical machine-readable output is available at `/v1/operations/agent-integrations`.

| Agent ID | Name | Pod/Tier | Bus Role | Data Systems |
|---|---|---|---|---|
| AGENT-01-PM | PM Agent | User Interface | Alpha/Omega/Rho; mission-state observer; heartbeat producer | redis, postgresql |
| AGENT-02-CEO | CEO Agent | Executive | Alpha/Beta/Delta/Omega/Rho/Sigma; publishes pod assignments/fusion requests; heartbeat producer | redis, postgresql |
| AGENT-03-BROKER | API Broker | Support Ring | Omega/Rho; traffic/routing directives and runtime incident signaling | redis, postgresql |
| AGENT-04-ACCOUNTANT | Accountant | Support Ring | Omega/Rho/Sigma; budget telemetry over mission-state streams | redis, postgresql |
| AGENT-05-SECURITY | Security Agent | Support Ring | Omega/Rho/Sigma; threat/compliance event monitoring | redis, postgresql, neo4j (planned optional) |
| AGENT-06-IS | IS Agent | Support Ring | Omega/Rho/Sigma; knowledge query/update broker for all pods | redis, postgresql, qdrant (reserved), neo4j (planned optional) |
| AGENT-07-VC | Version Control Agent | Support Ring | Omega/Rho/Sigma; provenance signaling and release trace control | redis, postgresql, object_storage (planned) |
| AGENT-08-COMPLIANCE | Compliance Agent | Support Ring | Omega/Rho/Sigma; policy and license conformance signals | redis, postgresql, neo4j (planned optional) |
| AGENT-09-HW | Hardware-Mapping Injector | Support Ring | Omega/Rho/Sigma; systems-pod optimization event consumer | redis, postgresql |
| AGENT-10-TESTER | System Integration Tester | Support Ring | Omega/Rho/Sigma; verification and incident signaling | redis, postgresql, object_storage (planned) |
| AGENT-11-DEPLOY | Deployment Agent | Support Ring | Omega/Rho/Sigma; consumes completion/ready signals, publishes build-ready | redis, postgresql, object_storage (planned) |
| AGENT-12-PODA-MGR | Pod A Sub-Manager | Pod A | Alpha/Beta/Delta/Rho; consumes podA assignment, publishes fusion/ready | redis, postgresql, qdrant (reserved), object_storage (planned) |
| AGENT-13-PODA-AUDIT | Pod A QC/Audit | Pod A | Delta/Sigma/Rho; verifies submitted artifacts; publish verified/rejected | redis, postgresql, qdrant (reserved), neo4j (planned optional), object_storage (planned) |
| AGENT-14-PYTHON | Python Specialist | Pod A | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-15-JAVASCRIPT | JavaScript Specialist | Pod A | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-16-RUBY | Ruby Specialist | Pod A | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-17-PHP | PHP Specialist | Pod A | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-18-PODB-MGR | Pod B Sub-Manager | Pod B | Alpha/Beta/Delta/Rho; consumes podB assignment, publishes fusion/ready | redis, postgresql, qdrant (reserved), object_storage (planned) |
| AGENT-19-PODB-AUDIT | Pod B QC/Audit | Pod B | Delta/Sigma/Rho; verifies submitted artifacts; publish verified/rejected | redis, postgresql, qdrant (reserved), neo4j (planned optional), object_storage (planned) |
| AGENT-20-C | C Specialist | Pod B | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-21-CPP | C++ Specialist | Pod B | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-22-RUST | Rust Specialist | Pod B | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-23-ZIG | Zig Specialist | Pod B | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-24-PODC-MGR | Pod C Sub-Manager | Pod C | Alpha/Beta/Delta/Rho; consumes podC assignment, publishes fusion/ready | redis, postgresql, qdrant (reserved), object_storage (planned) |
| AGENT-25-PODC-AUDIT | Pod C QC/Audit | Pod C | Delta/Sigma/Rho; verifies submitted artifacts; publish verified/rejected | redis, postgresql, qdrant (reserved), neo4j (planned optional), object_storage (planned) |
| AGENT-26-JAVA | Java Specialist | Pod C | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-27-CSHARP | C# Specialist | Pod C | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-28-SCALA | Scala Specialist | Pod C | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-29-KOTLIN | Kotlin Specialist | Pod C | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-30-PODD-MGR | Pod D Sub-Manager | Pod D | Alpha/Beta/Delta/Rho; consumes podD assignment, publishes fusion/ready | redis, postgresql, qdrant (reserved), object_storage (planned) |
| AGENT-31-PODD-AUDIT | Pod D QC/Audit | Pod D | Delta/Sigma/Rho; verifies submitted artifacts; publish verified/rejected | redis, postgresql, qdrant (reserved), neo4j (planned optional), object_storage (planned) |
| AGENT-32-MATLAB | MATLAB Specialist | Pod D | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-33-R | R Specialist | Pod D | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-34-JULIA | Julia Specialist | Pod D | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |
| AGENT-35-MATHEMATICA | Mathematica Specialist | Pod D | Beta/Delta/Sigma/Rho; consume running/assigned, publish RIR submission | redis, postgresql, qdrant (reserved) |

## Production Standards Recommendations

Redis:

- Use Redis Streams consumer groups with explicit acknowledgements for workload partitioning and replay safety.
- Enforce ACL-based authentication and TLS for all bus links.
- Configure persistence intentionally (RDB, AOF, or both) based on recovery objectives.

PostgreSQL:

- Control `max_connections` and reserve emergency slots; place PgBouncer in front of app workloads.
- Implement WAL archiving + base backups for PITR; regularly test restore workflows.
- Require TLS for service-to-database transport.

Neo4j (planned optional):

- Use key/uniqueness constraints on graph identifiers before production ingestion.
- Define and test backup/restore and consistency-check procedures before enabling critical paths.

Object storage (planned):

- Use versioned buckets and WORM-style retention (Object Lock equivalent) for immutable audit/binary evidence.
- Treat object-store paths and retention policies as first-class release controls.

## Next Phases

Phase 2: Redis and protocol hardening

- Add stream consumer-group lag metrics and pending-entry health checks.
- Enforce idempotent consumers where exactly-once semantics are required.
- Add bus-level chaos/recovery tests.

Phase 3: Postgres resilience controls

- Introduce PgBouncer profile and per-service pool settings.
- Add WAL archive pipeline and automated PITR drill script.
- Add migration safety gates for operational tables.

Phase 4: Knowledge path activation

- Move Qdrant from reserved endpoint into active specialist/audit retrieval path.
- Add knowledge query SLOs and cache hit-rate targets.

Phase 5: Neo4j and object storage expansion

- Add optional Neo4j adapter behind feature flag for relationship-heavy audit/compliance use cases.
- Add object storage adapter for immutable release bundles and audit evidence.
- Add retention, restore, and legal-hold style runbooks.

## Sources

Local sources:

- `C:\software\Holygrail\06_Agent_Architecture_Specification.md`
- `C:\software\Holygrail\07_Communication_Protocol_Specification.md`
- `C:\software\Holygrail\08_Data_Architecture_Document.md`
- `C:\software\Holygrail\20_Semantic_Bus_Implementation_Guide.md`
- `C:\software\Holygrail\21_Database_Setup_and_Schemas.md`
- `C:\software\Holygrail\29_Knowledge_Lake_Implementation_Guide.md`
- `C:\software\Holygrail\31_Agent_Communication_Patterns.md`
- `C:\software\Holygrail\theFactory\services\orchestrator\orchestrator\agent_registry.py`
- `C:\software\Holygrail\theFactory\protocol\topics.yaml`
- `C:\software\Holygrail\theFactory\BLUEPRINT_SPEC.md`

External production references:

- Redis XREADGROUP: https://redis.io/docs/latest/commands/xreadgroup/
- Redis security: https://redis.io/docs/latest/operate/oss_and_stack/management/security/
- Redis persistence: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- PostgreSQL connections/auth: https://www.postgresql.org/docs/current/runtime-config-connection.html
- PostgreSQL WAL archiving/PITR: https://www.postgresql.org/docs/current/continuous-archiving.html
- PostgreSQL TLS: https://www.postgresql.org/docs/current/ssl-tcp.html
- PgBouncer configuration: https://www.pgbouncer.org/config
- Neo4j constraints: https://neo4j.com/docs/cypher-manual/current/constraints/
- Neo4j backup/restore: https://neo4j.com/docs/operations-manual/current/backup-restore/
- Amazon S3 Object Lock: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- Amazon S3 consistency model: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html
