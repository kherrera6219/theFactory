# Documentation Index

Last updated: 2026-03-03

This index maps the in-repo documentation set for theFactory and reflects the current implementation baseline.

## Core Product and Architecture

- `ARCHITECTURE.md`: runtime topology, contracts, and control-plane architecture.
- `ROADMAP.md`: phased delivery status and current maturity plan.
- `PRODUCTION_PHASE_PLAN.md`: production hardening phases and exit criteria.
- `UPDATED_PHASE_PLAN_2026-03-03.md`: current post-Phase-18 execution plan and validation protocol.
- `GAP_ANALYSIS.md`: reviewed gaps, dispositions, and remaining structural work.
- `LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md`: explicit legacy-scope disposition and Mission Control port-policy reconciliation.

## Operations and Reliability

- `OPERATIONS_RUNBOOK.md`: health checks, smoke tests, auth checks, and DR operations.
- `OBSERVABILITY_STACK.md`: monitoring/telemetry stack baseline.
- `DEPLOYMENT_DR_PLAYBOOK.md`: deployment + disaster recovery operational playbook.
- `LONG_DURATION_RELIABILITY_QUALIFICATION.md`: sustained-load qualification method, thresholds, and baseline evidence.
- `TESTING_QUALITY_GATES.md`: enforced lint/test/coverage policy including core 100% module gates.
- `PRODUCTION_REVIEW_AUDIT.md`: checklist-aligned production audit updates and outcomes.
- `RELEASE_TRUST_PROMOTION_GATE.md`: CI attestation, promotion policy, and release-trust evidence flow.
- `evidence/phase23_langgraph_baseline_validation_2026-03-03.md`: LangGraph adoption baseline validation and quality-gate evidence.
- `evidence/phase24_langgraph_postgres_checkpointer_validation_2026-03-03.md`: Postgres checkpointer baseline validation for LangGraph mission lifecycle.
- `runbooks/semantic_bus_incident_runbook.md`: incident response playbook for MCP/Redis bus failures.
- `HGR_BACKEND_CHECKLIST_AUDIT_2026-03-02.md`: backend checklist gap audit and remediation sequence.

## Standards and External References

- `PRODUCTION_STANDARDS_REFERENCES.md`: official external standards and technical references.
- `AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md`: authoritative standards and evidence model for agent personas.
- `DATA_CLASSIFICATION_POLICY.md`: data handling classes and governance controls.

## Agent and Data-Plane Documentation

- `AGENT_SEMANTIC_BUS_DATA_SYSTEMS_PLAN.md`: agent protocol/data-system plan and phased data-plane evolution.
- `AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`: provider/model strategy by agent and thinking profile.

## UI/UX Planning and Reviews

- `UI_UX_WIREFRAME_FRONTEND_MASTER_PLAN.md`: frontend and wireframe completion plan.
- `UI_UX_PHASE_EXECUTION_LOG_2026-03-01.md`: UI/UX phase implementation log.
- `UX_USER_STORY_JOURNEY_INTERACTION_REVIEW_2026-03-01.md`: UX journey review and findings.

## API Contracts

- `openapi/api-gateway.v1.json`: exported API Gateway OpenAPI 3.1 contract.
- `openapi/orchestrator.v1.json`: exported Orchestrator OpenAPI 3.1 contract.
- `API_INTEGRATION_GUIDE.md`: authentication, examples, and integration behavior.

## Developer Enablement

- `DEVELOPER_ONBOARDING_GUIDE.md`: local setup and first-day validation flow.
- `../CHANGELOG.md`: implementation change history.

## Suggested Read Order

1. `../README.md`
2. `ARCHITECTURE.md`
3. `ROADMAP.md`
4. `OPERATIONS_RUNBOOK.md`
5. `AGENT_SEMANTIC_BUS_DATA_SYSTEMS_PLAN.md`
6. `AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`
7. `AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md`
