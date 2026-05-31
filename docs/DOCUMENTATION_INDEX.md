# Documentation Index

Document version: 2026.05.30  
Last updated: 2026-05-30  
Status: Canonical  
Audience: Operators, developers, maintainers, and auditors

This is the master map for theFactory documentation. The live documentation set follows [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md) and is organized by user need and operational ownership. Superseded material lives under `docs/archive/`.

## Start Here

1. [../README.md](../README.md)
2. [00_PRODUCT_OVERVIEW.md](00_PRODUCT_OVERVIEW.md)
3. [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md)
4. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
5. [ARCHITECTURE.md](ARCHITECTURE.md)
6. [ARCHITECTURE_DATA_FLOWS.md](ARCHITECTURE_DATA_FLOWS.md)
7. [REPOSITORY_BUILD_MAP_2026-03-29.md](REPOSITORY_BUILD_MAP_2026-03-29.md)
8. [RELEASE_COMPLETION_PLAN.md](RELEASE_COMPLETION_PLAN.md)
9. [../MIGRATION.md](../MIGRATION.md)
   - migration notes for semantic→protocol bus rename

## Product Identity, Doctrine, and Strategy

- [00_PRODUCT_OVERVIEW.md](00_PRODUCT_OVERVIEW.md)
  - five-minute product orientation
- [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md)
  - canonical positioning, scope boundaries, comparison to vibe coding
- [DEPENDENCY_ABSORPTION_DOCTRINE.md](DEPENDENCY_ABSORPTION_DOCTRINE.md)
  - dependency absorption doctrine, decision hierarchy, safety blocks
- [APPLICATION_INTELLIGENCE_MAP.md](APPLICATION_INTELLIGENCE_MAP.md)
  - application intelligence map artifact and consumers
- [RUNTIME_QC_AND_TEST_ENVIRONMENTS.md](RUNTIME_QC_AND_TEST_ENVIRONMENTS.md)
  - ephemeral test environments and AI runtime QC
- [SENSITIVE_CODE_HANDLING_POLICY.md](SENSITIVE_CODE_HANDLING_POLICY.md)
  - source code classification, provider routing, redaction
- [SCHEMA_REGISTRY_AND_VERSIONING.md](SCHEMA_REGISTRY_AND_VERSIONING.md)
  - schema registry, versioning rules, compatibility
- [LICENSE_STRATEGY.md](LICENSE_STRATEGY.md)
  - open-core strategy and MIT license confirmation

## Canonical Product and Architecture Docs

- [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md)
  - documentation conventions, archive rules, and quality gate
- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
  - shipped defaults, validation snapshot, and current follow-up work
- [ARCHITECTURE.md](ARCHITECTURE.md)
  - topology, services, data plane, and lifecycle baseline
- [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)
  - context, container, deployment, runtime, and trust-boundary diagrams
- [ARCHITECTURE_DATA_FLOWS.md](ARCHITECTURE_DATA_FLOWS.md)
  - mission, approval, artifact, identity, and telemetry flows
- [REPOSITORY_BUILD_MAP_2026-03-29.md](REPOSITORY_BUILD_MAP_2026-03-29.md)
  - generated full repository tree
- [ROADMAP.md](ROADMAP.md)
  - current roadmap and maturity direction
- [RELEASE_COMPLETION_PLAN.md](RELEASE_COMPLETION_PLAN.md)
  - production-release phase plan and out-of-band blockers
- [reviews/end-to-end-review-2026-04-15.md](reviews/end-to-end-review-2026-04-15.md)
  - latest end-to-end review closeout with resolved findings and live qualification evidence
- [reviews/review-todo-action-plan-2026-04-15.md](reviews/review-todo-action-plan-2026-04-15.md)
  - phase-based remediation closeout and remaining hardening follow-up

## Developer Documentation

- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
  - day-to-day engineering workflow
- [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md)
  - local setup and first-day validation
- [TESTING_QUALITY_GATES.md](TESTING_QUALITY_GATES.md)
  - test strategy, thresholds, and release checks
- [DIAGRAM_STANDARDS.md](DIAGRAM_STANDARDS.md)
  - required diagram types and conventions
- [../CONTRIBUTING.md](../CONTRIBUTING.md)
  - contribution workflow
- [../CHANGELOG.md](../CHANGELOG.md)
  - change history

## User and Operator Documentation

- [user/GETTING_STARTED.md](user/GETTING_STARTED.md)
  - first-success setup and basic workflows
- [user/OPERATOR_GUIDE.md](user/OPERATOR_GUIDE.md)
  - screen-by-screen operator instructions

## API and Reference Documentation

- [api/README.md](api/README.md)
  - API entry point and interactive docs
- [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md)
  - auth, examples, rate limits, and integration behavior
- [openapi/api-gateway.v1.json](openapi/api-gateway.v1.json)
  - gateway OpenAPI contract
- [openapi/orchestrator.v1.json](openapi/orchestrator.v1.json)
  - orchestrator OpenAPI contract

## Operations, Security, and Governance

- [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)
  - operational commands and validation procedures
- [DEPLOYMENT_DR_PLAYBOOK.md](DEPLOYMENT_DR_PLAYBOOK.md)
  - deployment and disaster-recovery process
- [OBSERVABILITY_STACK.md](OBSERVABILITY_STACK.md)
  - telemetry stack and alerting baseline
- [RELEASE_TRUST_PROMOTION_GATE.md](RELEASE_TRUST_PROMOTION_GATE.md)
  - release trust, attestation, and promotion checks
- [COMPOSE_ENVIRONMENT_PROFILES.md](COMPOSE_ENVIRONMENT_PROFILES.md)
  - environment profiles and compose behavior
- [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md)
  - data handling and classification rules
- [MODEL_PROMOTION_GOVERNANCE.md](MODEL_PROMOTION_GOVERNANCE.md)
  - AI model rollout and rollback governance
- [AGENT_SERVICE_KEY_ISOLATION.md](AGENT_SERVICE_KEY_ISOLATION.md)
  - internal key isolation and remaining hardening work
- [PRIVACY_POLICY.md](PRIVACY_POLICY.md)
  - privacy posture
- [TERMS_OF_SERVICE.md](TERMS_OF_SERVICE.md)
  - usage terms
- [ACCESSIBILITY_STATEMENT.md](ACCESSIBILITY_STATEMENT.md)
  - accessibility commitment and gaps

## Standards and Supporting References

- [PRODUCTION_STANDARDS_REFERENCES.md](PRODUCTION_STANDARDS_REFERENCES.md)
  - external standards and official references used by this repo
- [COMPLIANCE_EVIDENCE_MAPPING.md](COMPLIANCE_EVIDENCE_MAPPING.md)
  - control/evidence mapping
- [LEGACY_PROFILE_ID_MAPPING_INDEX.md](LEGACY_PROFILE_ID_MAPPING_INDEX.md)
  - legacy ID reference retained for compatibility analysis
- [AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md](AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md)
  - current provider/model matrix reference
- [AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md](AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md)
  - persona evidence model reference
- [AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md](AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md)
  - protocol bus and data-system reference plan

## ADRs

- [ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md](ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md)
- [ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md](ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md)
- [ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md](ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md)
- [ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md](ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md)
- [ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md](ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md)

## Evidence and Runbooks

- [evidence/](evidence/)
  - release qualification, audits, and phase evidence
- [runbooks/](runbooks/)
  - incident and recurring qualification procedures
- [protocol_bus_incident_runbook.md](runbooks/protocol_bus_incident_runbook.md)
  - Protocol Bus incident response (renamed from semantic_bus_incident_runbook.md)

## Archive

- [archive/README.md](archive/README.md)
  - archive policy and layout
- `archive/2026-03-29/`
  - superseded audits, planning artifacts, source `.docx` material, and legacy documentation bundles
