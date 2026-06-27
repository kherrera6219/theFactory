# theFactory Documentation Index

Document version: 2026.06.27-a
Last updated: 2026-06-27
Status: Canonical
Audience: All contributors

**Version:** 2026.06.27-a
**Maintained by:** Documentation Guild  
**Last reviewed:** 2026-06-27

This index maps the active theFactory documentation set. Historical source
material, superseded phase plans, run-specific evidence, and archived review
artifacts are intentionally kept under `docs/archive/` or `docs/evidence/` and
are not listed as current implementation truth unless called out explicitly.

---

## How to Use This Index

- **Operators** start with [Product Overview](#product--system-overview) and [Deployment & DR](#deployment--operations)
- **Developers** start with [Developer Onboarding](#developer-documentation) then branch to the subsystem they are working on
- **Architects** start with [Architecture](#architecture) and the ADR log
- **Security / Compliance** start with [Security & Compliance](#security--compliance)

---

## Product & System Overview

| File | Description | Audience |
|---|---|---|
| [README.md](README.md) | Docs landing page and current navigation guide for the GitHub `docs/` folder | All |
| [00_PRODUCT_OVERVIEW.md](00_PRODUCT_OVERVIEW.md) | Top-level product description, value proposition, and v1.2.0 feature set | All |
| [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) | Canonical positioning statement for current scope, non-goals, and evaluation boundaries | All |
| [BLUEPRINT_MAP.md](BLUEPRINT_MAP.md) | Full system blueprint — the single authoritative map of all services, agents, and data flows | All |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Current implementation status, test coverage, and known gaps by subsystem | All |
| [CURRENT_TODO.md](CURRENT_TODO.md) | Active TODO list and outstanding production-readiness work | Maintainers, Operators |
| [HANDOFF_CURRENT.md](HANDOFF_CURRENT.md) | Current handoff for maintainers and AI coding agents | Maintainers, AI coding agents |

---

## Architecture

| File | Description | Audience |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system architecture — services, data stores, agent topology, and deployment model | Architects, Developers |
| [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) | Mermaid/PlantUML architecture diagrams for all major subsystems | Architects |
| [ARCHITECTURE_DATA_FLOWS.md](ARCHITECTURE_DATA_FLOWS.md) | Detailed data flow diagrams for mission intake, processing, and completion | Architects, Developers |
| [diagrams/README.md](diagrams/README.md) | Diagram directory guide and maintenance expectations | Architects, Developers |
| [DIAGRAM_STANDARDS.md](DIAGRAM_STANDARDS.md) | Standards for creating and maintaining architecture diagrams | Developers |
| [APPLICATION_INTELLIGENCE_MAP.md](APPLICATION_INTELLIGENCE_MAP.md) | AIM generator — how the system produces a structured map of application intelligence from a mission | Architects, Developers |
| [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) | `mission_flow_v2/` package — the 11-phase state machine engine: all phase modules, MissionFlowContext, transition guards, recovery, and LangGraph vs v2 selection | Developers, Architects |

---

## Architecture Decision Records (ADRs)

| File | Decision | Date |
|---|---|---|
| [ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md](ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md) | Agent runtime topology — 41-agent, 4-pod, 4-tier structure | 2026-03-04 |
| [ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md](ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md) | Mission Flow v2 promoted to default; v1 retained as fallback | 2026-03-08 |
| [ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md](ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md) | Mission Flow v2 design and adoption plan | 2026-03-08 |
| [ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md](ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md) | API key auth chosen over OIDC for v1.2.0; OIDC deferred | 2026-03-04 |
| [ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md](ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md) | Catalogue of intentionally deferred scope items and rationale | 2026-03-08 |

---

## Developer Documentation

| File | Description | Audience |
|---|---|---|
| [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md) | Complete new-developer onboarding — environment setup, first run, test suite, contribution workflow | Developers |
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Day-to-day developer reference — common commands, service ports, env vars | Developers |
| [REPOSITORY_BUILD_MAP_2026-06-13.md](REPOSITORY_BUILD_MAP_2026-06-13.md) | Generated repository file and folder map required by documentation validation | Developers, Maintainers |
| [codex/DEFINITION_OF_DONE.md](codex/DEFINITION_OF_DONE.md) | Codex-oriented definition of done for repository work | Developers, Maintainers |
| [codex/REVIEW_CHECKLIST.md](codex/REVIEW_CHECKLIST.md) | Codex-oriented review checklist for implementation changes | Developers, Maintainers |
| [TESTING_QUALITY_GATES.md](TESTING_QUALITY_GATES.md) | Current test commands, quality gates, coverage policy, and release-check expectations | Developers, Maintainers |
| [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) | Full API reference for all Gateway and Orchestrator endpoints | Developers, Integrators |
| [api/README.md](api/README.md) | OpenAPI artifact index and generation notes | Developers, Integrators |
| [ERROR_CODES.md](ERROR_CODES.md) | Complete error code catalogue with causes and remediation steps | Developers, Operators |
| [ORCHESTRATOR_MAIN.md](ORCHESTRATOR_MAIN.md) | `main.py` reference — app.state keys, lifespan startup/shutdown sequence, all 6 background tasks, auth deps, direct endpoints, middleware, error handling, agent heuristics, and route module inventory | Developers |
| [RUNTIME_AND_AGENT_BASE.md](RUNTIME_AND_AGENT_BASE.md) | `runtime.py` execution engine (intake loop, lifecycle tasks, state events, self-heal) and `agent_base.py` class hierarchy (BaseAgent, 6 categories, 19 specialist classes, make_agent() factory) | Developers |
| [EQUIVALENCE_VERIFIER.md](EQUIVALENCE_VERIFIER.md) | Equivalence verification system — how the system proves behavioral equivalence between mission input and output | Developers |
| [IS_AGENT.md](IS_AGENT.md) | Integration Standards (IS) Agent — integration catalog and compliance checks | Developers |
| [DEMO_MISSION_SETUP.md](DEMO_MISSION_SETUP.md) | Step-by-step guide to setting up and running a demo mission | Developers, Operators |

---

## Configuration and Observability

| File | Description | Audience |
|---|---|---|
| [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md) | `settings.py` — complete reference for every `Settings` field, env var, default, and computed property; includes production hardening checklist | Developers, Operators |
| [TRACING.md](TRACING.md) | `tracing.py` — OpenTelemetry distributed tracing: `configure_tracing()`, `@trace_operation` decorator, sampling strategy, Jaeger setup, and log correlation | Developers, Operators |
| [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md) | Full observability stack — Prometheus metrics, Grafana dashboards, alert rules, and log aggregation | Operators, Developers |
| [METRICS_SOURCE_MODULES.md](METRICS_SOURCE_MODULES.md) | `data_plane_metrics.py` and `orchestrator_metrics.py` — all Prometheus counter/histogram/gauge definitions, label cardinality rules, Grafana dashboard mapping, and the metrics-to-alerting contract | Developers, Operators |

---

## Domain Models and Schema

| File | Description | Audience |
|---|---|---|
| [MODELS_AND_DOMAIN_SCHEMA.md](MODELS_AND_DOMAIN_SCHEMA.md) | `models.py` — all enums (MissionType, DepthMode, OutputMode, DataClassification), MissionState machine, VALID_TRANSITIONS map, EventType literals, and all Pydantic models (MissionRecord, MissionEvent, MissionCreate, MissionClarifyRequest, etc.) | Developers, Architects |
| [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md) | `logicnode_schema.py` — LogicNode dataclass, field glossary, confidence scoring bands, tag taxonomy (10 categories), language keys (20), pattern ID format, pod routing rules, storage contract, and evolution policy | Developers, Architects |
| [PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md](PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md) | Port coordinator and LogicNode schema compatibility reference | Developers, Architects |

---

## Storage Layer

| File | Description | Audience |
|---|---|---|
| [STORAGE_LAYER.md](STORAGE_LAYER.md) | Complete storage layer reference — `storage_core.py` (connection pool, migration entry, helpers), `storage.py` façade, and all 5 domain modules: missions, pods, logicnodes, artifacts, agents | Developers |
| [SCHEMA_REGISTRY_AND_VERSIONING.md](SCHEMA_REGISTRY_AND_VERSIONING.md) | Schema registry and DB versioning strategy — charter field embedding, migration governance, and backward-compatibility rules | Developers, Architects |

---

## API Routes

| File | Description | Audience |
|---|---|---|
| [ROUTES_REFERENCE.md](ROUTES_REFERENCE.md) | All three route modules — `missions.py` (mission CRUD and lifecycle), `operations.py` (dashboard and ops endpoints), `internal.py` (worker callback endpoints for LogicNodes, heartbeats, artifacts, audit) | Developers, Integrators |
| [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) | Full request/response examples for all public API endpoints | Developers, Integrators |

---

## LLM Integration and Prompt Engineering

| File | Description | Audience |
|---|---|---|
| [LLM_DELEGATION.md](LLM_DELEGATION.md) | `llm_delegation/` package — provider routing, retry/fallback, cost guard, offline mode, and adding new providers | Developers, Architects |
| [MODEL_PROMOTION_GOVERNANCE.md](MODEL_PROMOTION_GOVERNANCE.md) | Release-promotion rules for approved default and selectable model routes | Maintainers, AI operators |
| [PROMPT_REGISTRY_AND_ASSETS.md](PROMPT_REGISTRY_AND_ASSETS.md) | `prompt_registry.py` and `prompt_assets/` — versioned prompt vault, asset naming, SHA-256 fingerprinting, and audit traceability | Developers |
| [LLM_SAFETY_AND_DOCUMENT_PARSER.md](LLM_SAFETY_AND_DOCUMENT_PARSER.md) | LLM safety filters and document parser — input/output sanitization and safe parsing for mission payloads | Developers, Security |
| [AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md](AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md) | Current per-agent LLM defaults and the approved Mission Control 3-model catalog | Architects, Developers |
| [AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md](AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md) | Evidence that all 41 agent personas meet the persona standards defined in `agent_personas.py` | Architects |

---

## Agent System

| File | Description | Audience |
|---|---|---|
| [AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md](AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md) | Protocol Bus — 6-stream Redis Streams architecture (alpha/beta/delta/sigma/omega/rho) and data system plan | Architects, Developers |
| [AGENT_SCALING_AND_HEARTBEAT.md](AGENT_SCALING_AND_HEARTBEAT.md) | Agent scaling strategy and heartbeat service — how agents are scaled and health-monitored | Operators, Developers |
| [AGENT_SERVICE_KEY_ISOLATION.md](AGENT_SERVICE_KEY_ISOLATION.md) | Service key isolation — per-agent credential isolation model and enforcement | Security, Developers |
| [KNOWLEDGE_LAKE_AND_EMBEDDINGS.md](KNOWLEDGE_LAKE_AND_EMBEDDINGS.md) | Knowledge Lake — PostgreSQL-first documentation store with optional Qdrant semantic mirror; three embedding providers (Gemini/OpenAI/deterministic), semantic search gate, and `task_type` contract | Developers, Architects |
| [DEPENDENCY_ABSORPTION_DOCTRINE.md](DEPENDENCY_ABSORPTION_DOCTRINE.md) | Dependency Absorption — the doctrine of eliminating unnecessary dependencies and the DEPABS agent implementation | Developers, Architects |

---

## Security & Compliance

| File | Description | Audience |
|---|---|---|
| [SECURITY_COMPLIANCE_MODULE.md](SECURITY_COMPLIANCE_MODULE.md) | `security_compliance.py` — runtime enforcement of data classification tiers, sensitive pattern detection, and `local_only` agent enforcement for Tier 3 missions | Security, Developers |
| [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) | Data classification tiers and handling requirements for all data types in theFactory | Security, Compliance |
| [COMPLIANCE_EVIDENCE_MAPPING.md](COMPLIANCE_EVIDENCE_MAPPING.md) | Maps compliance controls (SOC2, ISO 27001) to evidence artifacts in the system | Compliance, Security |
| [SENSITIVE_CODE_HANDLING_POLICY.md](SENSITIVE_CODE_HANDLING_POLICY.md) | Sensitive code handling policy — detection rules, escalation thresholds, and operator override procedures | Security, Developers |
| [LICENSE_STRATEGY.md](LICENSE_STRATEGY.md) | Open-source license strategy and dependency license compliance | Legal, Developers |
| [ACCESSIBILITY_STATEMENT.md](ACCESSIBILITY_STATEMENT.md) | Accessibility statement for the Mission Control UI | Product, Legal |

---

## Supporting Modules

| File | Description | Audience |
|---|---|---|
| [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) | Reference for all smaller orchestrator modules: `migrations.py`, `auth.py`, `review_policy.py`, `protocol.py`, `project_identity.py`, `hw_agent.py`, `testdata_agent.py`, `system_maintenance.py`, `agent_integrations.py`, `port_coordinator.py` | Developers |

---

## Deployment & Operations

| File | Description | Audience |
|---|---|---|
| [DEPLOYMENT_DR_PLAYBOOK.md](DEPLOYMENT_DR_PLAYBOOK.md) | Deployment and Disaster Recovery playbook — full runbooks for deploy, rollback, and DR scenarios | Operators |
| [COMPOSE_ENVIRONMENT_PROFILES.md](COMPOSE_ENVIRONMENT_PROFILES.md) | Docker Compose environment profiles — which profile to use for local dev, staging, and production | Developers, Operators |
| [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) | Day-to-day operations runbook — incident response, alert triage, and escalation procedures | Operators |
| [RELEASE_TRUST_PROMOTION_GATE.md](RELEASE_TRUST_PROMOTION_GATE.md) | Release trust gate, attestation expectations, and promotion evidence requirements | Maintainers, Operators |
| [RUNTIME_QC_AND_TEST_ENVIRONMENTS.md](RUNTIME_QC_AND_TEST_ENVIRONMENTS.md) | Runtime QC system and test environment management | Developers, Operators |
| [runbooks/dr_validation_runbook.md](runbooks/dr_validation_runbook.md) | Disaster-recovery validation procedure | Operators |
| [runbooks/protocol_bus_incident_runbook.md](runbooks/protocol_bus_incident_runbook.md) | Protocol Bus incident triage and recovery procedure | Operators |
| [runbooks/dedicated_agent_canary_runbook.md](runbooks/dedicated_agent_canary_runbook.md) | Dedicated-agent canary validation procedure | Operators |
| [runbooks/optional_data_plane_incident_runbook.md](runbooks/optional_data_plane_incident_runbook.md) | Optional data-plane incident triage procedure | Operators |
| [runbooks/qualification_matrix_runbook.md](runbooks/qualification_matrix_runbook.md) | Qualification matrix execution and evidence procedure | Operators, Maintainers |

---

## User and Legal Documentation

| File | Description | Audience |
|---|---|---|
| [user/GETTING_STARTED.md](user/GETTING_STARTED.md) | First-run operator guide for local Mission Control usage | Operators |
| [user/OPERATOR_GUIDE.md](user/OPERATOR_GUIDE.md) | Mission Control operator workflows and runtime operations | Operators |
| [PRIVACY_POLICY.md](PRIVACY_POLICY.md) | Product privacy policy | Legal, Operators |
| [TERMS_OF_SERVICE.md](TERMS_OF_SERVICE.md) | Product terms of service | Legal, Operators |

---

## Standards & Supporting References

| File | Description | Audience |
|---|---|---|
| [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md) | Standards for writing and maintaining theFactory documentation | All contributors |
| [DIAGRAM_STANDARDS.md](DIAGRAM_STANDARDS.md) | Standards for creating and maintaining architecture diagrams | Developers |
| [PRODUCTION_STANDARDS_REFERENCES.md](PRODUCTION_STANDARDS_REFERENCES.md) | Production standards and external reference standards cited in theFactory design | Architects, Developers |
| [LOCAL_FIRST_COMPLIANCE_PLAN.md](LOCAL_FIRST_COMPLIANCE_PLAN.md) | Local-first compliance plan — how theFactory meets compliance requirements in fully air-gapped deployments | Security, Compliance |

---

## Documentation Coverage Status

All high, medium, and low priority undocumented modules have been resolved. The tracker below is the full historical record and current status.

| Code File | Priority | Status | Doc |
|---|---|---|---|
| `models.py` | 🔴 High | ✅ Documented | [MODELS_AND_DOMAIN_SCHEMA.md](MODELS_AND_DOMAIN_SCHEMA.md) |
| `mission_flow_v2/__init__.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/lifecycle.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/base.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/transitions.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/phases_intake.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/phases_build.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/phases_runtime.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `mission_flow_v2/phases_delivery.py` | 🔴 High | ✅ Documented | [MISSION_FLOW_V2.md](MISSION_FLOW_V2.md) |
| `storage_missions.py` | 🟠 Medium | ✅ Documented | [STORAGE_LAYER.md](STORAGE_LAYER.md) |
| `storage_agents.py` | 🟠 Medium | ✅ Documented | [STORAGE_LAYER.md](STORAGE_LAYER.md) |
| `storage_artifacts.py` | 🟠 Medium | ✅ Documented | [STORAGE_LAYER.md](STORAGE_LAYER.md) |
| `storage_core.py` + `storage.py` | 🟠 Medium | ✅ Documented | [STORAGE_LAYER.md](STORAGE_LAYER.md) |
| `storage_pods.py` | 🟠 Medium | ✅ Documented | [STORAGE_LAYER.md](STORAGE_LAYER.md) |
| `security_compliance.py` | 🟠 Medium | ✅ Documented | [SECURITY_COMPLIANCE_MODULE.md](SECURITY_COMPLIANCE_MODULE.md) |
| `routes/internal.py` | 🟠 Medium | ✅ Documented | [ROUTES_REFERENCE.md](ROUTES_REFERENCE.md) |
| `routes/operations.py` | 🟠 Medium | ✅ Documented | [ROUTES_REFERENCE.md](ROUTES_REFERENCE.md) |
| `routes/missions.py` | 🟠 Medium | ✅ Documented | [ROUTES_REFERENCE.md](ROUTES_REFERENCE.md) |
| `llm_delegation/` (package) | 🟠 Medium | ✅ Documented | [LLM_DELEGATION.md](LLM_DELEGATION.md) |
| `prompt_registry.py` + `prompt_assets/` | 🟠 Medium | ✅ Documented | [PROMPT_REGISTRY_AND_ASSETS.md](PROMPT_REGISTRY_AND_ASSETS.md) |
| `llm_safety.py` | 🟠 Medium | ✅ Documented | [LLM_SAFETY_AND_DOCUMENT_PARSER.md](LLM_SAFETY_AND_DOCUMENT_PARSER.md) |
| `logicnode_schema.py` | 🟠 Medium | ✅ Documented | [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md) |
| `data_plane_metrics.py` | 🟠 Medium | ✅ Documented | [METRICS_SOURCE_MODULES.md](METRICS_SOURCE_MODULES.md) |
| `orchestrator_metrics.py` | 🟠 Medium | ✅ Documented | [METRICS_SOURCE_MODULES.md](METRICS_SOURCE_MODULES.md) |
| `aim_generator.py` | 🟠 Medium | ✅ Documented | [APPLICATION_INTELLIGENCE_MAP.md](APPLICATION_INTELLIGENCE_MAP.md) |
| `agent_scaling.py` | 🟠 Medium | ✅ Documented | [AGENT_SCALING_AND_HEARTBEAT.md](AGENT_SCALING_AND_HEARTBEAT.md) |
| `heartbeat_service.py` | 🟠 Medium | ✅ Documented | [AGENT_SCALING_AND_HEARTBEAT.md](AGENT_SCALING_AND_HEARTBEAT.md) |
| `settings.py` | 🔴 High | ✅ Documented | [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md) |
| `tracing.py` | 🟠 Medium | ✅ Documented | [TRACING.md](TRACING.md) |
| `port_coordinator.py` | 🟠 Medium | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `agent_integrations.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `migrations.py` + `migrations/` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `auth.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `review_policy.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `hw_agent.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `testdata_agent.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `system_maintenance.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `protocol.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |
| `project_identity.py` | 🟡 Low | ✅ Documented | [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md) |

> The documentation gap tracker is now fully clear. Every orchestrator module is documented. New undocumented modules should be added here as they are introduced.
