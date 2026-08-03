# Design Traceability Matrix

Document version: 2026.08.01
Last updated: 2026-08-01
Status: Canonical
Audience: Maintainers, architects, auditors, and AI coding agents

One row per numbered design document (01–64) from the Feb–Mar 2026 Holy Grail
Refinery design corpus, mapped to its status and the module(s) that implement it.

**Purpose.** Before this file, the only way to answer *"Doc 30 specified a registry
— where is it?"* was to read 64 design documents against a live codebase. For a
system whose selling point is auditability, that was the conspicuous absence
(audit §6.4).

**How to read the status column.** Verdicts match
[ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md),
which is the governing document and outranks this one wherever they differ:

- **Implemented** — design intent exists in shipped code; may exceed the design
- **Superseded** — deliberately replaced by a different approach; a closed decision,
  not a gap
- **Deferred** — still wanted, not built, with a named revisit trigger
- **Partial** — core built, a named sub-capability is Superseded or Deferred

**Source corpus location.** The numbered documents are archived at
`docs/archive/2026-03-29/legacy-workspace/root-legacy-documentation/`. They are
historical from 2026-08-01 and must not be read as current specification.

**This is not `BLUEPRINT_MAP.md`.** That file maps the repository's own layout.
This one maps *design intent* to *implementation*.

---

## Product & strategy (01–04)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 01 | Product Requirements | **Partial** | `models.py` mission taxonomy, whole pipeline | §1.3's "zero dependencies / smelted into core logic" is **Superseded** (ADR D2). The functional requirements are met; the binary promise is retired |
| 02 | Technical Vision | **Superseded** | — | Describes the 14→4→1 comprehension model and binary synthesis. Superseded by ADR rows 11 and 14 |
| 03 | Market & Competitive Analysis | **Superseded** | — | Positioning predates the product's category change to governed generation/modernisation. See [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) |
| 04 | Product Roadmap & Phasing | **Superseded** | — | Replaced by [CURRENT_TODO.md](CURRENT_TODO.md) and [UPGRADE_RECONCILIATION_PLAN_2026-08-01.md](UPGRADE_RECONCILIATION_PLAN_2026-08-01.md) |

## Core architecture (05–09)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 05 | System Architecture | **Partial** | `agent_registry.py`, `mission_flow_v2/` | Tier/pod structure **Implemented and exceeded** (41 agents vs 35). §1.1's parallel four-pod extraction and the per-agent context-isolation principle are **Superseded** (ADR rows 14, 16) |
| 06 | Agent Architecture Specification | **Implemented** | `agent_registry.py`, `agent_personas.py`, `agent_base.py` | Naming convention, tier labels, and sub-manager/auditor/specialist triad match exactly; adds `runtime_class` honesty field |
| 07 | Communication Protocol Specification | **Partial** | `services/protocol-bus-mcp/protocol_bus/mcp_server.py`, `protocol_bus_producer.py` | Six lanes **Implemented and exceeded** (HMAC signing, dedup, replay rejection, backpressure, DLQ). §1.2's bus-as-control-plane is **Deferred** to Phase 6/EDCP; §2's envelope is **Superseded** (ADR rows 4, 5) |
| 08 | Data Architecture | **Implemented** | `qdrant_store.py`, `milvus_store.py`, `neo4j_store.py`, `knowledge_lake.py`, `llm_cost_ledger.py`, migrations V001–V009 | All five designed stores on real engines. V009 immutable-audit control exceeds §4.6 |
| 09 | Refined-IR Specification | **Partial** | `schemas/rir.fn.schema.json`, `pod-worker/refined_ir.py` | Schema **Implemented** faithfully. The producer was templated until Phase 4 (2026-08-01), which delivered real typed signatures, a real op stream, and side-effect-derived purity for AST-backed languages — §3 type system and §5 side effects now have persisted representation for Python/Java/Haskell. §4 constraints and §7 composition still do not. §8 equivalence *execution* remains **Superseded** pending Phase 5 (ADR rows 7, 8) |

## Pod specifications (10–13)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 10 | Pod A — Dynamic Languages | **Implemented** | `agent_registry.py` Pod A | 4 specialists (python, javascript, ruby, php) |
| 11 | Pod B — Systems | **Implemented** | `agent_registry.py` Pod B | 5 specialists — includes Go, which `HolyGrail_Design_Checklist.md` placed in Pod C |
| 12 | Pod C — Enterprise | **Implemented** | `agent_registry.py` Pod C | 4 specialists (java, csharp, scala, kotlin) |
| 13 | Pod D — Mathematical Languages | **Superseded** | `agent_registry.py` Pod D | Contains 6 specialists including Haskell and OCaml — functional, not mathematical. Rename to "Mathematical & Functional" is UPG-23 (ADR row 18) |

## Orchestration & UI (14–15)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 14 | Workflow Orchestration Design | **Superseded** | `mission_flow_v2/transitions.py`, `lifecycle.py` | 678 lines of LangGraph per-agent state machines, never written. Live engine is a hand-rolled mission-level transition table; `LANGGRAPH_ENABLED=false`. Formal disposition is UPG-71 (ADR row 13) |
| 15 | Mission Control UI Specification | **Partial** | `apps/mission-control/app/(shell)/` | 15+ routes against 9 designed panels, with axe-core, Lighthouse CI, Playwright. §3.1's LogicNode dependency graph is **Deferred** to UPG-70 — no dependency data exists to draw until Phase 3 (ADR row 17) |

## Build & environment (16–19)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 16 | Development Environment Setup | **Implemented** | `Makefile`, `scripts/`, [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md) | |
| 17 | Docker Containerization Guide | **Implemented** | `deploy/docker-compose.yaml` + overlays | Exceeds design: `no-new-privileges`, `cap_drop: ALL`, read-only rootfs + tmpfs, TLS for Redis/Postgres |
| 18 | Local Infrastructure Configuration | **Implemented** | `deploy/`, `.env` contract | |
| 19 | Agent Base Classes & Templates | **Implemented** | `agent_base.py`, `agent_personas.py` | |

## Platform services (20–22)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 20 | Semantic Bus Implementation | **Deferred** | — | Embedding-based routing. Stage 4 of [PROTOCOL_BUS_PROGRAM_ROADMAP.md](PROTOCOL_BUS_PROGRAM_ROADMAP.md); correctly depends on EDCP completing first |
| 21 | Database Setup & Schemas | **Implemented** | `migrations/V001`–`V009`, `ledger/schema.sql` | |
| 22 | API Layer Design | **Implemented** | `services/api-gateway/`, `docs/openapi/` | Dual-mode auth exceeds the design's JWT-only assumption |

## Quality & delivery (23–28)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 23 | Testing Framework & QA | **Implemented** | `tests/` (~130 pytest files), Vitest, Playwright | Exceeds design; adds golden-fixture extraction locks and `tests/eval/` prompt-safety evals |
| 24 | CI/CD Pipeline Configuration | **Implemented** | `.github/workflows/` | Exceeds design: SBOM (SPDX + CycloneDX), Bandit, pip-audit, GPL/AGPL license blocking, fail-closed promotion gate |
| 25 | Monitoring & Observability | **Implemented** | `deploy/monitoring/`, [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md) | Prometheus/Grafana/Loki/Jaeger |
| 26 | Security Implementation & Hardening | **Implemented** | `shared_runtime/prompt_guard.py`, `pii_guard.py`, `crypto_signing.py`, `agent_auth.py` | Exceeds every dimension of the design (ADR row 15) |
| 27 | Agent Deployment & Operations | **Implemented** | `deploy/docker-compose.full-dedicated-agents.yaml`, `services/agent-runtime/` | Three topologies: condensed, dedicated, full-dedicated |
| 28 | Development Workflow Best Practices | **Implemented** | `AGENTS.md`, `CONTRIBUTING.md` | |

## Knowledge & registry (29–31)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 29 | Knowledge Lake Implementation | **Implemented** | `knowledge_lake.py`, `qdrant_store.py`, `milvus_store.py` | |
| 30 | LogicNode Registry Implementation | **Deferred** | `mission_logicnodes` table only | 1,635 lines — the largest unimplemented spec in the corpus. No cross-mission registry, versioning, clustering, or semantic search. **Revisit trigger: Phase 4 `ast_v1` projections cover a majority of missions** (ADR row 10, UPG-73) |
| 31 | Agent Communication Patterns | **Partial** | `protocol_bus_producer.py`, `mission_flow_v2/lifecycle.py` | Patterns exist as producers; the subscribe-and-activate model is Deferred with Doc 07 §1.2 |

## Operations (32–40)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 32 | Production Deployment Guide | **Implemented** | `deploy/docker-compose.prod.yaml`, [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) | Production guards raise `RuntimeError` rather than warn |
| 33 | System Maintenance Procedures | **Implemented** | `system_maintenance.py`, [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) | |
| 34 | Backup & Recovery Operations | **Implemented** | `scripts/restore_postgres.ps1`, `scripts/run_automated_dr_drill.py` | Dry-run-by-default since remediation Phase 1 |
| 35 | Scaling & Performance Tuning | **Partial** | `agent_scaling.py` | `AGENT_SCALING_ENABLED` gated; distributed execution Deferred per [ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md](ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md) |
| 36 | Incident Response Playbook | **Implemented** | [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) | |
| 37 | Monitoring Dashboard Configuration | **Implemented** | `deploy/monitoring/grafana/` | |
| 38 | Log Aggregation & Analysis | **Implemented** | `shared_runtime/logging_config.py`, Loki | JSON structured logging |
| 39 | Alerting & Notification | **Implemented** | `deploy/monitoring/prometheus/rules/thefactory-alerts.yml` | |
| 40 | Disaster Recovery Testing | **Implemented** | `scripts/run_automated_dr_drill.py`, `scripts/dr_drill.ps1` | |

## Test strategy (41–50)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 41 | Unit Testing Standards | **Implemented** | `tests/services/` | |
| 42 | Integration Testing Framework | **Implemented** | `tests/integration/` | |
| 43 | End-to-End Testing Scenarios | **Implemented** | `apps/mission-control/e2e/` | Seven mission scenarios plus Electron |
| 44 | Performance Testing & Benchmarking | **Partial** | `tests/load/` Locust profile | Live Phase 13 performance proof still outstanding |
| 45 | Load & Stress Testing | **Partial** | `tests/load/` | As above |
| 46 | Security Testing & Vulnerability Assessment | **Implemented** | `tests/services/test_state_mutation_auth.py`, Bandit, pip-audit, CodeQL, Trivy | |
| 47 | Audit Agent Testing Procedures | **Implemented** | `services/audit-worker/audit_worker/main.py`, audit tests | |
| 48 | Test Data Management & Seeding | **Implemented** | `AGENT-40-TESTDATA`, `tests/fixtures/` | Ephemeral test data was not in the design |
| 49 | Regression Testing Strategy | **Implemented** | golden fixtures under `tests/fixtures/extractors/` | |
| 50 | Continuous Testing Strategy | **Implemented** | `.github/workflows/` | |

## Developer & extension guides (51–54)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 51 | Developer Onboarding | **Implemented** | [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md) | |
| 52 | API Documentation Reference | **Implemented** | `docs/openapi/`, drift check in CI | |
| 53 | Agent Development Guide | **Implemented** | `agent_base.py`, [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) | |
| 54 | Protocol Extension Guide | **Implemented** | `protocol/topics.yaml`, `mcp_server.py` | |

## Reference & release (55–58)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 55 | Glossary & Terminology | **Superseded** | — | Defines "smelting", "Master Logic Stream", and the 0.0001% tolerance — all retired (ADR rows 9, 14) |
| 56 | Architecture Decision Records | **Superseded** | `docs/ADR_*.md` | Replaced by the repository's live ADR set, including this reconciliation |
| 57 | FAQ | **Superseded** | [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) | Answers describe the retired product category |
| 58 | Changelog & Release Notes | **Implemented** | `CHANGELOG.md` | |

## User-facing (59–64)

| Doc | Title | Status | Implementing module(s) | Evidence / note |
|---|---|---|---|---|
| 59 | User Guide | **Partial** | [user/GETTING_STARTED.md](user/GETTING_STARTED.md), [user/OPERATOR_GUIDE.md](user/OPERATOR_GUIDE.md) | Rewritten for the current product |
| 60 | System Administrator Guide | **Implemented** | [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md), [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md) | |
| 61 | User Stories & Use Cases | **Superseded** | — | Written against the multi-language smelting workflow |
| 62 | User Interaction Guide | **Implemented** | Mission Control chat intake, PM clarification cards | |
| 63 | Graphics & Visual Design Style Guide | **Implemented** | `apps/mission-control/app/globals.css`, design tokens | |
| 64 | User-Facing IDE Interface Specification | **Partial** | Mission Control + VS Code launch action | No embedded IDE; the product opens the operator's own VS Code against the output folder |

---

## Capabilities built with no design document

These have no row above because no design document specifies them. They are the
reason the divergences are defensible, and per audit §5 they should be written into
the specification rather than left as undocumented surplus.

| Capability | Module | Specification status |
|---|---|---|
| Mission taxonomy (10 types, 5 depth modes, 8 output modes, 4 classifications) | `models.py` | **Unwritten** — largest unspecified surface in the system; UPG-72 |
| Dependency absorption | `dependency_absorption.py` (`AGENT-39-DEPABS`) | [DEPENDENCY_ABSORPTION_DOCTRINE.md](DEPENDENCY_ABSORPTION_DOCTRINE.md) |
| Runtime QC in a hardened sandbox | `rqca_agent.py` (`AGENT-41-RQCA`) | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| Ephemeral test data | `AGENT-40-TESTDATA` | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| Application Intelligence Map & Mission Charter | `aim_generator.py`, `schemas/mission_charter.v1.json` | Both were flagged missing in the May-2026 gap report; both are live |
| Real AST extraction (design assumed LLM-based) | `pod-worker/ast_extractor.py`, `js_ast_extractor.py`, `java_ast_extractor.py` | Deterministic where the design was probabilistic |
| Cryptographic chain-of-custody | `shared_runtime/crypto_signing.py`, migrations V008/V009 | Stronger than Doc 08 §4.6 |
| Desktop distribution | `apps/mission-control/` Electron + NSIS | Not in the design at all |
| Pre-flight toolchain validation | `pod-worker/toolchains.py` | Retained under ADR D2 — validation, not synthesis |

---

## Maintenance

Update this file whenever a design area changes verdict. A verdict change requires
an amendment to
[ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md)
first — the ADR governs, this matrix reflects it.
