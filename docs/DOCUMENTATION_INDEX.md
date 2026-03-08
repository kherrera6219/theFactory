# Documentation Index

Last updated: 2026-03-08

This index maps the in-repo documentation set for theFactory and reflects the current implementation baseline.

## Core Product and Architecture

- `ARCHITECTURE.md`: runtime topology, contracts, and control-plane architecture.
- `ROADMAP.md`: phased delivery status and current maturity plan.
- `PRODUCTION_PHASE_PLAN.md`: production hardening phases and exit criteria.
- `UPDATED_PHASE_PLAN_2026-03-03.md`: current post-Phase-18 execution plan and validation protocol.
- `ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md`: canonical decision record for condensed vs dedicated-agent runtime topology.
- `ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md`: canonical security-model decision record for API-key, hybrid, and OIDC modes.
- `ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md`: canonical status decision for v1.1 production runtime vs v2 roadmap scope.
- `GAP_ANALYSIS.md`: reviewed gaps, dispositions, and remaining structural work.
- `LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md`: explicit legacy-scope disposition and Mission Control port-policy reconciliation.
- `WORD_DOC_AUDIT_2026-03-03.md`: reconciliation audit against all in-repo Word-document requirements.
- `UPDATED_TODO_FROM_WORD_AUDIT_2026-03-03.md`: prioritized backlog generated from Word-doc audit findings.
- `SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md`: deterministic 7-phase Smelt-cycle mapping policy for runtime telemetry.
- `MISSION_FLOW_V1_1_CANONICAL_2026-03-07.md`: canonical reconciliation of root mission-flow Word doc aliases to runtime 35-agent IDs and lifecycle behavior.
- `MISSION_FLOW_V2_COMPARISON_2026-03-08.md`: gap audit comparing `HGR_Mission_Flow_v2.docx` against canonical mission flow and live runtime behavior.

## Operations and Reliability

- `OPERATIONS_RUNBOOK.md`: health checks, smoke tests, auth checks, and DR operations.
- `OBSERVABILITY_STACK.md`: monitoring/telemetry stack baseline.
- `DEPLOYMENT_DR_PLAYBOOK.md`: deployment + disaster recovery operational playbook.
- `LONG_DURATION_RELIABILITY_QUALIFICATION.md`: sustained-load qualification method, thresholds, and baseline evidence.
- `../scripts/mission_artifact_qualification.py`: live mission artifact integrity qualification (chain trace + pod assignment + logicnodes).
- `TESTING_QUALITY_GATES.md`: enforced lint/test/coverage policy including core 100% module gates.
- `PRODUCTION_REVIEW_AUDIT.md`: checklist-aligned production audit updates and outcomes.
- `RELEASE_TRUST_PROMOTION_GATE.md`: CI attestation, promotion policy, and release-trust evidence flow.
- `evidence/phase23_langgraph_baseline_validation_2026-03-03.md`: LangGraph adoption baseline validation and quality-gate evidence.
- `evidence/phase24_langgraph_postgres_checkpointer_validation_2026-03-03.md`: Postgres checkpointer baseline validation for LangGraph mission lifecycle.
- `evidence/phase25_word_doc_audit_and_langgraph_runtime_visibility_2026-03-03.md`: Word-doc audit execution and LangGraph runtime visibility validation.
- `evidence/phase26_langgraph_live_recovery_validation_2026-03-03.md`: lifecycle rehydration hardening and live restart qualification summary.
- `evidence/phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json`: machine-readable live qualification timings and pass/fail criteria.
- `evidence/phase27_mission_control_live_transport_validation_2026-03-04.md`: live SSE transport validation for critical Mission Control views.
- `evidence/phase28_smelt_cycle_runtime_reconciliation_validation_2026-03-04.md`: deterministic 7-phase runtime reconciliation validation.
- `evidence/phase29_topology_and_security_adr_validation_2026-03-04.md`: topology/security decision-package validation and sweep results.
- `evidence/phase30_auth_mode_and_dedicated_profile_validation_2026-03-04.md`: auth-mode execution baseline and dedicated-profile scaffolding validation.
- `evidence/phase31_dedicated_agent_binding_scheduler_validation_2026-03-04.md`: dedicated-agent binding scheduler enforcement and validation sweep evidence.
- `evidence/phase32_optional_data_plane_observability_validation_2026-03-04.md`: optional adapter observability, alerting, and dashboard validation evidence.
- `evidence/phase33_extended_data_plane_live_qualification_validation_2026-03-04.md`: live Neo4j/MinIO qualification and disruption-recovery validation evidence.
- `evidence/phase34_mission_control_advanced_operator_ux_validation_2026-03-04.md`: repo diff-review/apply gate and high-volume UI virtualization validation evidence.
- `evidence/phase35_mission_artifact_runtime_integrity_validation_2026-03-08.md`: mission artifact integrity qualification tooling, tests, and validation sweep outcomes.
- `evidence/phase36_frontend_budget_a11y_enforcement_2026-03-08.md`: CI Lighthouse budget enforcement, full axe color-contrast validation, and live mission chain/artifact integration proof.
- `evidence/mission_artifact_qualification_shared_2026-03-08.json`: shared-topology live artifact qualification result.
- `evidence/mission_artifact_qualification_dedicated_2026-03-08.json`: dedicated-topology live artifact qualification result.
- `runbooks/semantic_bus_incident_runbook.md`: incident response playbook for MCP/Redis bus failures.
- `runbooks/optional_data_plane_incident_runbook.md`: incident response playbook for Neo4j/object-storage optional adapter degradation.
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
