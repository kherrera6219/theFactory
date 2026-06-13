# Repository Build Map

Document version: 2026.03.29
Generated at: 2026-03-30T02:03:48+00:00
Repository root: `C:\software\Holygrail\theFactory`

This map is generated from the current filesystem so it can be reproduced and reviewed as code.

## Inclusion Rules

- Includes all files and folders under the repository root except cache/vendor directories that are not part of the maintained application source tree.
- Excludes `.claude`, `.git`, `.pytest_cache`, `.ruff_cache`, `.next`, `.venv`, `node_modules`, `playwright-report`, `test-results`, and `__pycache__` directories.
- Paths are shown exactly as present at generation time.

## Summary

- Directories included: `134`
- Files included: `642`

## Tree

```text
theFactory
├── .github
│   ├── ISSUE_TEMPLATE
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── security_report.md
│   ├── workflows
│   │   ├── ci.yml
│   │   ├── qualification.yml
│   │   └── security.yml
│   ├── CODEOWNERS
│   └── PULL_REQUEST_TEMPLATE.md
├── apps
│   └── mission-control
│       ├── .lighthouseci
│       ├── app
│       │   ├── (shell)
│       │   │   ├── agents
│       │   │   │   └── page.tsx
│       │   │   ├── alerts
│       │   │   │   └── page.tsx
│       │   │   ├── builder
│       │   │   │   └── page.tsx
│       │   │   ├── chat
│       │   │   │   └── page.tsx
│       │   │   ├── dashboard
│       │   │   │   └── page.tsx
│       │   │   ├── databases
│       │   │   │   └── page.tsx
│       │   │   ├── logicnodes
│       │   │   │   └── page.tsx
│       │   │   ├── missions
│       │   │   │   ├── [id]
│       │   │   │   │   └── page.tsx
│       │   │   │   └── page.tsx
│       │   │   ├── performance
│       │   │   │   └── page.tsx
│       │   │   ├── projects
│       │   │   │   └── page.tsx
│       │   │   ├── repo
│       │   │   │   └── page.tsx
│       │   │   ├── semantic-bus
│       │   │   │   └── page.tsx
│       │   │   ├── settings
│       │   │   │   └── page.tsx
│       │   │   ├── error.tsx
│       │   │   ├── layout.tsx
│       │   │   ├── loading.tsx
│       │   │   └── page.tsx
│       │   ├── api
│       │   │   ├── builder
│       │   │   │   └── review
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   ├── operator
│       │   │   │   └── mission-state
│       │   │   │       └── route.ts
│       │   │   ├── repo
│       │   │   │   ├── import
│       │   │   │   │   ├── route.test.ts
│       │   │   │   │   └── route.ts
│       │   │   │   ├── review
│       │   │   │   │   ├── route.test.ts
│       │   │   │   │   └── route.ts
│       │   │   │   └── shared.ts
│       │   │   ├── review
│       │   │   │   └── approve
│       │   │   │       ├── route.test.ts
│       │   │   │       └── route.ts
│       │   │   └── vault
│       │   │       ├── test
│       │   │       │   ├── route.test.ts
│       │   │       │   └── route.ts
│       │   │       ├── auth.test.ts
│       │   │       ├── auth.ts
│       │   │       ├── route.test.ts
│       │   │       └── route.ts
│       │   ├── components
│       │   │   ├── keyboard-shortcuts.tsx
│       │   │   ├── page-header.tsx
│       │   │   ├── panel.tsx
│       │   │   ├── reconnect-banner.tsx
│       │   │   └── shell-nav.tsx
│       │   ├── lib
│       │   │   ├── server
│       │   │   │   ├── vault.test.ts
│       │   │   │   └── vault.ts
│       │   │   ├── test
│       │   │   │   └── server-only.ts
│       │   │   ├── api-client.test.ts
│       │   │   ├── api-client.ts
│       │   │   ├── format.ts
│       │   │   ├── language.test.ts
│       │   │   ├── language.ts
│       │   │   ├── mock-data.ts
│       │   │   ├── navigation.ts
│       │   │   ├── security.ts
│       │   │   ├── smelt-cycle.test.ts
│       │   │   ├── smelt-cycle.ts
│       │   │   ├── template-catalog.ts
│       │   │   └── types.ts
│       │   ├── error.tsx
│       │   ├── generated-tokens.css
│       │   ├── globals.css
│       │   ├── layout.tsx
│       │   └── not-found.tsx
│       ├── e2e
│       │   └── mission-control.spec.ts
│       ├── public
│       │   └── .gitkeep
│       ├── scripts
│       │   └── sync-design-tokens.mjs
│       ├── .dockerignore
│       ├── .env.example
│       ├── .gitignore
│       ├── Dockerfile
│       ├── lighthouserc.json
│       ├── lint_errors.txt
│       ├── next-env.d.ts
│       ├── next.config.mjs
│       ├── package-lock.json
│       ├── package.json
│       ├── playwright.config.ts
│       ├── README.md
│       ├── temp_extract.py
│       ├── tsconfig.json
│       ├── tsconfig.tsbuildinfo
│       └── vitest.config.ts
├── assets
│   └── design-tokens
│       ├── tokens.css
│       └── tokens.json
├── backups
│   ├── ulr_20990101_16972898.sql.json
│   ├── ulr_20990101_16972898.sql.sha256
│   ├── ulr_20990101_2bd307f5.sql.json
│   ├── ulr_20990101_2bd307f5.sql.sha256
│   ├── ulr_20990101_c92508a2.sql.json
│   ├── ulr_20990101_c92508a2.sql.sha256
│   ├── ulr_20990101_e518e53a.sql.json
│   └── ulr_20990101_e518e53a.sql.sha256
├── config
│   └── agent_api_keys.yaml
├── deploy
│   ├── .local
│   │   ├── postgres-certs
│   │   │   ├── ca.crt
│   │   │   ├── server.crt
│   │   │   └── server.key
│   │   └── redis-certs
│   │       ├── ca.crt
│   │       ├── redis.crt
│   │       └── redis.key
│   ├── monitoring
│   │   ├── alertmanager
│   │   │   └── alertmanager.yml
│   │   ├── grafana
│   │   │   └── provisioning
│   │   │       ├── dashboards
│   │   │       │   ├── json
│   │   │       │   │   └── thefactory-overview.json
│   │   │       │   └── dashboards.yml
│   │   │       └── datasources
│   │   │           └── datasources.yml
│   │   ├── loki
│   │   │   └── loki-config.yml
│   │   ├── prometheus
│   │   │   ├── rules
│   │   │   │   └── thefactory-alerts.yml
│   │   │   └── prometheus.yml
│   │   └── promtail
│   │       └── promtail-config.yml
│   ├── postgres
│   │   ├── certs
│   │   ├── entrypoint.sh
│   │   └── postgresql.conf
│   ├── redis
│   │   ├── certs
│   │   └── redis.conf
│   ├── docker-compose.dev.yaml
│   ├── docker-compose.full-dedicated-agents.yaml
│   ├── docker-compose.monitoring.yaml
│   ├── docker-compose.prod.yaml
│   ├── docker-compose.staging.yaml
│   ├── docker-compose.yaml
│   └── promotion-policy.json
├── docs
│   ├── api
│   │   └── README.md
│   ├── archive
│   │   ├── 2026-03-29
│   │   │   ├── historical
│   │   │   │   ├── COMPLETION_TODO_2026-03-02.md
│   │   │   │   ├── COMPLETION_TODO_2026-03-13.md
│   │   │   │   ├── COMPREHENSIVE_APPLICATION_AUDIT_2026-03-02.md
│   │   │   │   ├── DELIVERY_PHASE_LOG_2026-03-02.md
│   │   │   │   ├── GAP_ANALYSIS.md
│   │   │   │   ├── HGR_BACKEND_CHECKLIST_AUDIT_2026-03-02.md
│   │   │   │   ├── LEGACY_ROADMAP_RECONCILIATION_2026-03-03.md
│   │   │   │   ├── MISSION_FLOW_V1_1_CANONICAL_2026-03-07.md
│   │   │   │   ├── MISSION_FLOW_V2_COMPARISON_2026-03-08.md
│   │   │   │   ├── PRODUCTION_PHASE_PLAN.md
│   │   │   │   ├── PRODUCTION_REVIEW_AUDIT.md
│   │   │   │   ├── UI_UX_PHASE_EXECUTION_LOG_2026-03-01.md
│   │   │   │   ├── UI_UX_WIREFRAME_FRONTEND_MASTER_PLAN.md
│   │   │   │   ├── UPDATED_PHASE_PLAN_2026-03-03.md
│   │   │   │   ├── UPDATED_TODO_FROM_WORD_AUDIT_2026-03-03.md
│   │   │   │   ├── UX_USER_STORY_JOURNEY_INTERACTION_REVIEW_2026-03-01.md
│   │   │   │   ├── WORD_DOC_APP_REMAINING_AUDIT_2026-03-08.md
│   │   │   │   ├── WORD_DOC_APP_REMAINING_TODO_2026-03-08.md
│   │   │   │   └── WORD_DOC_AUDIT_2026-03-03.md
│   │   │   ├── legacy-workspace
│   │   │   │   ├── docs-legacy-documentation
│   │   │   │   │   ├── agent_profile_SPECIALIST_AI_001.docx
│   │   │   │   │   ├── agent_profiles_batch5.docx
│   │   │   │   │   ├── agent_profiles_batch6.docx
│   │   │   │   │   ├── agent_profiles_batch7.docx
│   │   │   │   │   └── agent_profiles_batch8_FINAL.docx
│   │   │   │   ├── root-legacy-documentation
│   │   │   │   │   ├── unified-logic-refinery-blueprint-single
│   │   │   │   │   │   └── unified-logic-refinery-starter
│   │   │   │   │   │       ├── deploy
│   │   │   │   │   │       │   └── docker-compose.yaml
│   │   │   │   │   │       ├── examples
│   │   │   │   │   │       │   ├── logicnode.example.json
│   │   │   │   │   │       │   ├── rir.fn.example.json
│   │   │   │   │   │       │   └── rir.module.example.json
│   │   │   │   │   │       ├── ledger
│   │   │   │   │   │       │   └── schema.sql
│   │   │   │   │   │       ├── protocol
│   │   │   │   │   │       │   └── topics.yaml
│   │   │   │   │   │       ├── schemas
│   │   │   │   │   │       │   ├── event.envelope.schema.json
│   │   │   │   │   │       │   ├── logicnode.schema.json
│   │   │   │   │   │       │   ├── rir.fn.schema.json
│   │   │   │   │   │       │   └── rir.module.schema.json
│   │   │   │   │   │       ├── scripts
│   │   │   │   │   │       │   └── validate_schemas.py
│   │   │   │   │   │       ├── services
│   │   │   │   │   │       │   ├── dashboard
│   │   │   │   │   │       │   │   ├── dashboard
│   │   │   │   │   │       │   │   │   ├── __init__.py
│   │   │   │   │   │       │   │   │   └── main.py
│   │   │   │   │   │       │   │   ├── Dockerfile
│   │   │   │   │   │       │   │   └── requirements.txt
│   │   │   │   │   │       │   └── orchestrator
│   │   │   │   │   │       │       ├── orchestrator
│   │   │   │   │   │       │       │   ├── __init__.py
│   │   │   │   │   │       │       │   └── main.py
│   │   │   │   │   │       │       ├── Dockerfile
│   │   │   │   │   │       │       └── requirements.txt
│   │   │   │   │   │       ├── BLUEPRINT.md
│   │   │   │   │   │       ├── BLUEPRINT_SPEC.md
│   │   │   │   │   │       ├── Makefile
│   │   │   │   │   │       └── README.md
│   │   │   │   │   ├── unified-logic-refinery-starter
│   │   │   │   │   │   └── unified-logic-refinery-starter
│   │   │   │   │   │       ├── deploy
│   │   │   │   │   │       │   └── docker-compose.yaml
│   │   │   │   │   │       ├── examples
│   │   │   │   │   │       │   ├── logicnode.example.json
│   │   │   │   │   │       │   ├── rir.fn.example.json
│   │   │   │   │   │       │   └── rir.module.example.json
│   │   │   │   │   │       ├── ledger
│   │   │   │   │   │       │   └── schema.sql
│   │   │   │   │   │       ├── protocol
│   │   │   │   │   │       │   └── topics.yaml
│   │   │   │   │   │       ├── schemas
│   │   │   │   │   │       │   ├── event.envelope.schema.json
│   │   │   │   │   │       │   ├── logicnode.schema.json
│   │   │   │   │   │       │   ├── rir.fn.schema.json
│   │   │   │   │   │       │   └── rir.module.schema.json
│   │   │   │   │   │       ├── scripts
│   │   │   │   │   │       │   └── validate_schemas.py
│   │   │   │   │   │       ├── services
│   │   │   │   │   │       │   ├── dashboard
│   │   │   │   │   │       │   │   ├── dashboard
│   │   │   │   │   │       │   │   │   ├── __init__.py
│   │   │   │   │   │       │   │   │   └── main.py
│   │   │   │   │   │       │   │   ├── Dockerfile
│   │   │   │   │   │       │   │   └── requirements.txt
│   │   │   │   │   │       │   └── orchestrator
│   │   │   │   │   │       │       ├── orchestrator
│   │   │   │   │   │       │       │   ├── __init__.py
│   │   │   │   │   │       │       │   └── main.py
│   │   │   │   │   │       │       ├── Dockerfile
│   │   │   │   │   │       │       └── requirements.txt
│   │   │   │   │   │       ├── BLUEPRINT_SPEC.md
│   │   │   │   │   │       ├── Makefile
│   │   │   │   │   │       └── README.md
│   │   │   │   │   ├── # PART 8 PROFESSIONAL GROUNDING & C.txt
│   │   │   │   │   ├── # Pod D Mathematical Pod - Complete.txt
│   │   │   │   │   ├── 00_Documentation_Index.md
│   │   │   │   │   ├── 00_Documentation_Index.txt
│   │   │   │   │   ├── 00_Documentation_Index.txt.md
│   │   │   │   │   ├── 01_Product_Requirements_Document.md
│   │   │   │   │   ├── 02_Technical_Vision_Document.md
│   │   │   │   │   ├── 03_Market_Competitive_Analysis.md
│   │   │   │   │   ├── 04_Product_Roadmap_Phasing_Strategy.md
│   │   │   │   │   ├── 05_System_Architecture_Document.md
│   │   │   │   │   ├── 06_Agent_Architecture_Specification.md
│   │   │   │   │   ├── 07_Communication_Protocol_Specification.md
│   │   │   │   │   ├── 08_Data_Architecture_Document.md
│   │   │   │   │   ├── 09_Refined_IR_Specification.md
│   │   │   │   │   ├── 10_Pod_A_Dynamic_Languages_Specification.md
│   │   │   │   │   ├── 11_Pod_B_Systems_Specification.md
│   │   │   │   │   ├── 12_Pod_C_Enterprise_Specification.md
│   │   │   │   │   ├── 13_Pod_D_Mathematical_Languages_Specification.md
│   │   │   │   │   ├── 14_Workflow_Orchestration_Design.md
│   │   │   │   │   ├── 15_Mission_Control_UI_Specification.md
│   │   │   │   │   ├── 16_Development_Environment_Setup.md
│   │   │   │   │   ├── 17_Docker_Containerization_Guide.md
│   │   │   │   │   ├── 18_Local_Infrastructure_Configuration_AW1.md
│   │   │   │   │   ├── 19_Agent_Base_Classes_Templates.md
│   │   │   │   │   ├── 20_Semantic_Bus_Implementation_Guide.md
│   │   │   │   │   ├── 21_Database_Setup_and_Schemas.md
│   │   │   │   │   ├── 22_API_Layer_Design_Implementation.md
│   │   │   │   │   ├── 23_Testing_Framework_Quality_Assurance.md
│   │   │   │   │   ├── 24_CICD_Pipeline_Configuration.md
│   │   │   │   │   ├── 25_Monitoring_Observability_Implementation.md
│   │   │   │   │   ├── 26_Security_Implementation_Hardening.md
│   │   │   │   │   ├── 27_Agent_Deployment_Operations_Guide.md
│   │   │   │   │   ├── 28_Development_Workflow_Best_Practices.md
│   │   │   │   │   ├── 29_Knowledge_Lake_Implementation_Guide.md
│   │   │   │   │   ├── 30_LogicNode_Registry_Implementation.md
│   │   │   │   │   ├── 31_Agent_Communication_Patterns.md
│   │   │   │   │   ├── 32_Production_Deployment_Guide.md
│   │   │   │   │   ├── 33_System_Maintenance_Procedures.md
│   │   │   │   │   ├── 34_Backup_Recovery_Operations.md
│   │   │   │   │   ├── 35_Scaling_Performance_Tuning.md
│   │   │   │   │   ├── 36_Incident_Response_Playbook.md
│   │   │   │   │   ├── 37_System_Monitoring_Dashboard_Configuration.md
│   │   │   │   │   ├── 38_Log_Aggregation_Analysis_Setup.md
│   │   │   │   │   ├── 39_Alerting_Notification_System.md
│   │   │   │   │   ├── 40_Disaster_Recovery_Testing_Procedures.md
│   │   │   │   │   ├── 41_Unit_Testing_Standards_Implementation.md
│   │   │   │   │   ├── 42_Integration_Testing_Framework.md
│   │   │   │   │   ├── 43_End_to_End_Testing_Scenarios.md
│   │   │   │   │   ├── 44_Performance_Testing_Benchmarking.md
│   │   │   │   │   ├── 45_Load_Testing_Stress_Testing.md
│   │   │   │   │   ├── 46_Security_Testing_Vulnerability_Assessment.md
│   │   │   │   │   ├── 47_Audit_Agent_Testing_Procedures.md
│   │   │   │   │   ├── 48_Test_Data_Management_Seeding.md
│   │   │   │   │   ├── 49_Regression_Testing_Strategy.md
│   │   │   │   │   ├── 50_Continuous_Testing_Strategy.md
│   │   │   │   │   ├── 51_Developer_Onboarding_Guide.md
│   │   │   │   │   ├── 52_API_Documentation_Reference.md
│   │   │   │   │   ├── 53_Agent_Development_Guide.md
│   │   │   │   │   ├── 54_Protocol_Extension_Guide.md
│   │   │   │   │   ├── 55_Glossary_Terminology_Reference.md
│   │   │   │   │   ├── 56_Architecture_Decision_Records_ADRs.md
│   │   │   │   │   ├── 57_FAQ_Document.md
│   │   │   │   │   ├── 58_Changelog_Release_Notes.md
│   │   │   │   │   ├── 59_User_Guide.md
│   │   │   │   │   ├── 60_System_Administrator_Guide.md
│   │   │   │   │   ├── 61_User_Stories_Use_Cases.md
│   │   │   │   │   ├── 62_User_Interaction_Guide.md
│   │   │   │   │   ├── 63_Graphics_Visual_Design_Style_Guide.md
│   │   │   │   │   ├── 64_User_Facing_IDE_Interface_Specification.md
│   │   │   │   │   ├── 8.txt
│   │   │   │   │   ├── AGENT-C-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-CPP-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-CS-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-GO-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-JAVA-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-PHP-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-RUBY-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-RUST-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-SCALA-001_Complete_Profile.md
│   │   │   │   │   ├── AGENT-ZIG-001_Complete_Profile.md
│   │   │   │   │   ├── agent1.txt
│   │   │   │   │   ├── agentsnotes2.txt
│   │   │   │   │   ├── AUDIT-CORRECTNESS-001_Complete_Profile.md
│   │   │   │   │   ├── AUDIT-LEAD-001_Complete_Profile.md
│   │   │   │   │   ├── AUDIT-PERF-001_Complete_Profile.md
│   │   │   │   │   ├── core idea.txt
│   │   │   │   │   ├── holy grail notes 1.txt
│   │   │   │   │   ├── holy grail notes 2.txt
│   │   │   │   │   ├── holy_grail_notes_1.txt
│   │   │   │   │   ├── LANGUAGE_AGENTS_BATCH.md
│   │   │   │   │   ├── MANAGER-POD-B-001_Complete_Profile.md
│   │   │   │   │   ├── MANAGER-POD-C-001_Complete_Profile.md
│   │   │   │   │   ├── MANAGER-POD-D-001_Complete_Profile.md
│   │   │   │   │   ├── master notes.txt
│   │   │   │   │   ├── New chatSearchChatsProjectsArtifact.txt
│   │   │   │   │   ├── notes 2.txt
│   │   │   │   │   ├── notes3.txt
│   │   │   │   │   ├── notes4.txt
│   │   │   │   │   ├── Part_8_Professional_Grounding_Reference.md
│   │   │   │   │   ├── plan.txt
│   │   │   │   │   ├── Pod A Manager.txt
│   │   │   │   │   ├── pod b setup.txt
│   │   │   │   │   ├── pod1.txt
│   │   │   │   │   ├── pod_b_setup.txt
│   │   │   │   │   ├── pod_c_complete.txt
│   │   │   │   │   ├── pod_c_detailed_specification.txt
│   │   │   │   │   ├── pod_d_mathematical_spec.md
│   │   │   │   │   ├── podnotes.txt
│   │   │   │   │   ├── PROFILE_COMPLETION_STATUS.md
│   │   │   │   │   ├── profile_creation_summary.md
│   │   │   │   │   ├── protocol_alpha_directive.md
│   │   │   │   │   ├── protocol_beta_production.md
│   │   │   │   │   ├── protocol_delta_sigma_audit_knowledge.md
│   │   │   │   │   ├── protocol_omega_rho_user_traffic.md
│   │   │   │   │   ├── Security Audit Agent.txt
│   │   │   │   │   ├── SUPPORT-DEVOPS-001_Complete_Profile.md
│   │   │   │   │   ├── Untitled.txt
│   │   │   │   │   ├── Untitled1.txt
│   │   │   │   │   ├── Untitled11.txt
│   │   │   │   │   ├── Untitled13.txt
│   │   │   │   │   ├── Untitled3.txt
│   │   │   │   │   ├── Untitled6.txt
│   │   │   │   │   └── Untitled9.txt
│   │   │   │   └── tmp_docs
│   │   │   │       ├── HGR_Backend_Checklist_v3_Final.docx.md
│   │   │   │       ├── HGR_Mission_Flow_v1_1.txt
│   │   │   │       ├── HGR_Mission_Flow_v2.txt
│   │   │   │       ├── HolyGrail_Development_Standards.docx.md
│   │   │   │       ├── HolyGrail_Frontend_Design_3.docx.md
│   │   │   │       ├── HolyGrail_Production_Review_Checklist.docx.md
│   │   │   │       └── HolyGrail_Style_Guide.docx.md
│   │   │   └── source-docx
│   │   │       ├── HGR_Agent_Model_Register.docx
│   │   │       ├── HGR_Backend_Checklist_v3_Final.docx
│   │   │       ├── HGR_Mission_Flow.docx
│   │   │       ├── HGR_Mission_Flow_v1_1.docx
│   │   │       ├── HGR_Mission_Flow_v2.docx
│   │   │       ├── HolyGrail_Design_Checklist.docx
│   │   │       ├── HolyGrail_Development_Standards.docx
│   │   │       ├── HolyGrail_Frontend_Design_3.docx
│   │   │       ├── HolyGrail_Production_Review_Checklist.docx
│   │   │       └── HolyGrail_Style_Guide.docx
│   │   └── README.md
│   ├── evidence
│   │   ├── canary-runs
│   │   │   ├── dedicated_agent_canary_julia_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_julia_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_kotlin_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_python_20260308T043002Z.json
│   │   │   ├── dedicated_agent_canary_python_20260308T173500Z.json
│   │   │   ├── dedicated_agent_canary_rust_20260308T043002Z.json
│   │   │   └── dedicated_agent_canary_rust_20260308T173500Z.json
│   │   ├── agent_model_inventory_latest.json
│   │   ├── dedicated_agent_canary_full_dedicated_strict_2026-03-09.json
│   │   ├── dedicated_agent_canary_trend_2026-03-08.json
│   │   ├── dedicated_agent_canary_trend_history.jsonl
│   │   ├── dedicated_agent_canary_trend_latest.json
│   │   ├── frontend_style_guide_compliance_2026-03-03.md
│   │   ├── langgraph_postgres_recovery_qualification_latest.json
│   │   ├── langgraph_v2_prototype_matrix_2026-03-08.json
│   │   ├── langgraph_v2_prototype_matrix_history.jsonl
│   │   ├── langgraph_v2_prototype_matrix_latest.json
│   │   ├── mission_artifact_qualification_dedicated_2026-03-08.json
│   │   ├── mission_artifact_qualification_full_dedicated_strict_2026-03-09.json
│   │   ├── mission_artifact_qualification_history.jsonl
│   │   ├── mission_artifact_qualification_latest.json
│   │   ├── mission_artifact_qualification_shared_2026-03-08.json
│   │   ├── mission_artifact_qualification_v1_1_latest.json
│   │   ├── operator_route_oidc_matrix_2026-03-08.json
│   │   ├── operator_route_oidc_matrix_history.jsonl
│   │   ├── operator_route_oidc_matrix_latest.json
│   │   ├── phase12_builder_repo_validation_2026-03-03.md
│   │   ├── phase13_script_validation_2026-03-03.md
│   │   ├── phase14_legacy_reconciliation_2026-03-03.md
│   │   ├── phase15_live_integration_validation_2026-03-03.md
│   │   ├── phase16_data_system_activation_validation_2026-03-03.md
│   │   ├── phase17_neo4j_feature_flag_validation_2026-03-03.md
│   │   ├── phase18_object_storage_validation_2026-03-03.md
│   │   ├── phase23_langgraph_baseline_validation_2026-03-03.md
│   │   ├── phase24_langgraph_postgres_checkpointer_validation_2026-03-03.md
│   │   ├── phase25_word_doc_audit_and_langgraph_runtime_visibility_2026-03-03.md
│   │   ├── phase26_langgraph_live_recovery_validation_2026-03-03.md
│   │   ├── phase26_langgraph_postgres_live_recovery_qualification_2026-03-03.json
│   │   ├── phase27_mission_control_live_transport_validation_2026-03-04.md
│   │   ├── phase28_smelt_cycle_runtime_reconciliation_validation_2026-03-04.md
│   │   ├── phase29_topology_and_security_adr_validation_2026-03-04.md
│   │   ├── phase30_auth_mode_and_dedicated_profile_validation_2026-03-04.md
│   │   ├── phase31_dedicated_agent_binding_scheduler_validation_2026-03-04.md
│   │   ├── phase32_optional_data_plane_observability_validation_2026-03-04.md
│   │   ├── phase33_extended_data_plane_live_qualification_validation_2026-03-04.md
│   │   ├── phase34_mission_control_advanced_operator_ux_validation_2026-03-04.md
│   │   ├── phase35_mission_artifact_runtime_integrity_validation_2026-03-08.md
│   │   ├── phase36_frontend_budget_a11y_enforcement_2026-03-08.md
│   │   ├── phase37_strategy_auth_canary_2026-03-08.md
│   │   ├── phase38_qualification_matrix_automation_2026-03-08.md
│   │   ├── phase39_llm_node_wiring_hardening_2026-03-08.md
│   │   ├── phase40_supply_chain_and_secret_hygiene.md
│   │   ├── phase41_build_and_package_artifact_pipeline.md
│   │   ├── phase42_shared_state_and_api_convergence.md
│   │   ├── phase43_ai_safety_prompt_governance_eval_gates.md
│   │   ├── phase44_infrastructure_backup_restore_incident_readiness.md
│   │   ├── phase45_mission_control_convergence_and_final_release_qualification.md
│   │   ├── pod_language_extraction_2026-03-03.md
│   │   ├── qualification_gate_summary_latest.json
│   │   ├── reliability_qualification_baseline_2026-03-03.json
│   │   └── word_doc_extraction_2026-03-08.json
│   ├── openapi
│   │   ├── api-gateway.v1.json
│   │   └── orchestrator.v1.json
│   ├── runbooks
│   │   ├── dedicated_agent_canary_runbook.md
│   │   ├── optional_data_plane_incident_runbook.md
│   │   ├── qualification_matrix_runbook.md
│   │   └── semantic_bus_incident_runbook.md
│   ├── user
│   │   ├── GETTING_STARTED.md
│   │   └── OPERATOR_GUIDE.md
│   ├── ACCESSIBILITY_STATEMENT.md
│   ├── ADR_35_AGENT_RUNTIME_TOPOLOGY_2026-03-04.md
│   ├── ADR_MISSION_FLOW_V2_STATUS_2026-03-08.md
│   ├── ADR_SECURITY_MODEL_API_KEY_VS_OIDC_2026-03-04.md
│   ├── ADR_STRATEGIC_DEFERRED_SCOPE_DECISIONS_2026-03-08.md
│   ├── ADR_V2_MISSION_FLOW_ADOPTION_DESIGN_2026-03-08.md
│   ├── AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md
│   ├── AGENT_PERSONA_STANDARDS_EVIDENCE_2026-03-02.md
│   ├── AGENT_SEMANTIC_BUS_DATA_SYSTEMS_PLAN.md
│   ├── AGENT_SERVICE_KEY_ISOLATION.md
│   ├── API_INTEGRATION_GUIDE.md
│   ├── ARCHITECTURE.md
│   ├── ARCHITECTURE_DATA_FLOWS.md
│   ├── ARCHITECTURE_DIAGRAMS.md
│   ├── COMPLIANCE_EVIDENCE_MAPPING.md
│   ├── COMPOSE_ENVIRONMENT_PROFILES.md
│   ├── DATA_CLASSIFICATION_POLICY.md
│   ├── DEPLOYMENT_DR_PLAYBOOK.md
│   ├── DEVELOPER_GUIDE.md
│   ├── DEVELOPER_ONBOARDING_GUIDE.md
│   ├── DIAGRAM_STANDARDS.md
│   ├── DOCUMENTATION_INDEX.md
│   ├── DOCUMENTATION_STANDARDS.md
│   ├── IMPLEMENTATION_STATUS.md
│   ├── LEGACY_PROFILE_ID_MAPPING_INDEX.md
│   ├── LONG_DURATION_RELIABILITY_QUALIFICATION.md
│   ├── MODEL_PROMOTION_GOVERNANCE.md
│   ├── OBSERVABILITY_STACK.md
│   ├── OPERATIONS_RUNBOOK.md
│   ├── PRIVACY_POLICY.md
│   ├── PRODUCTION_STANDARDS_REFERENCES.md
│   ├── RELEASE_COMPLETION_PLAN.md
│   ├── RELEASE_TRUST_PROMOTION_GATE.md
│   ├── REPOSITORY_BUILD_MAP_2026-03-29.md
│   ├── ROADMAP.md
│   ├── SMELT_CYCLE_RUNTIME_MAPPING_2026-03-04.md
│   ├── TERMS_OF_SERVICE.md
│   └── TESTING_QUALITY_GATES.md
├── examples
│   ├── logicnode.example.json
│   ├── rir.fn.example.json
│   └── rir.module.example.json
├── ledger
│   └── schema.sql
├── protocol
│   └── topics.yaml
├── reports
│   ├── dr-drill-latest.json
│   ├── master_audit_2026-03-29.md
│   └── promotion-decision.local.json
├── schemas
│   ├── event.envelope.schema.json
│   ├── logicnode.schema.json
│   ├── rir.fn.schema.json
│   └── rir.module.schema.json
├── scripts
│   ├── backup_postgres.ps1
│   ├── build_refined_ir_catalog.py
│   ├── check_coverage_thresholds.py
│   ├── debug_sweep.ps1
│   ├── dedicated_agent_canary_rollout.ps1
│   ├── dedicated_agent_canary_rollout.py
│   ├── dedicated_agent_canary_trend.ps1
│   ├── dedicated_agent_canary_trend.py
│   ├── dora_metrics_summary.py
│   ├── dr_drill.ps1
│   ├── export_agent_model_inventory.py
│   ├── export_openapi.py
│   ├── generate_agent_service_keys.py
│   ├── generate_build_map.py
│   ├── generate_dev_tls_certs.ps1
│   ├── generate_dev_tls_certs.sh
│   ├── generate_postgres_tls_certs.py
│   ├── langgraph_postgres_recovery_qualification.ps1
│   ├── langgraph_postgres_recovery_qualification.py
│   ├── langgraph_v2_prototype_matrix.ps1
│   ├── langgraph_v2_prototype_matrix.py
│   ├── mission_artifact_qualification.ps1
│   ├── mission_artifact_qualification.py
│   ├── normalize_document_headers.py
│   ├── operator_route_auth_matrix_qualification.ps1
│   ├── operator_route_auth_matrix_qualification.py
│   ├── perf_smoke.ps1
│   ├── perf_smoke.py
│   ├── pre_deploy_check.ps1
│   ├── production_review_audit.py
│   ├── promotion_gate.py
│   ├── qualification_gate_summary.py
│   ├── reliability_qualification.ps1
│   ├── reliability_qualification.py
│   ├── restore_postgres.ps1
│   ├── validate_documentation.py
│   ├── validate_schemas.py
│   ├── verify_backup_artifacts.py
│   └── verify_release_evidence.py
├── services
│   ├── agent-runtime
│   │   ├── agent_runtime
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── api-gateway
│   │   ├── api_gateway
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── audit-worker
│   │   ├── audit_worker
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── dashboard
│   │   ├── dashboard
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── orchestrator
│   │   ├── orchestrator
│   │   │   ├── migrations
│   │   │   │   ├── V001_initial_runtime_schema.sql
│   │   │   │   ├── V002_build_artifact_runtime_schema.sql
│   │   │   │   └── V003_review_approval_runtime_schema.sql
│   │   │   ├── __init__.py
│   │   │   ├── agent_base.py
│   │   │   ├── agent_integrations.py
│   │   │   ├── agent_personas.py
│   │   │   ├── agent_registry.py
│   │   │   ├── agent_scaling.py
│   │   │   ├── auth.py
│   │   │   ├── build_artifacts.py
│   │   │   ├── data_plane_metrics.py
│   │   │   ├── langgraph_lifecycle.py
│   │   │   ├── llm_delegation.py
│   │   │   ├── main.py
│   │   │   ├── migrations.py
│   │   │   ├── milvus_store.py
│   │   │   ├── mission_flow.py
│   │   │   ├── mission_flow_v2.py
│   │   │   ├── models.py
│   │   │   ├── neo4j_store.py
│   │   │   ├── object_store.py
│   │   │   ├── protocol.py
│   │   │   ├── qdrant_store.py
│   │   │   ├── runtime.py
│   │   │   ├── settings.py
│   │   │   ├── storage.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── pod-worker
│   │   ├── pod_worker
│   │   │   ├── __init__.py
│   │   │   ├── concept_catalog.py
│   │   │   ├── language_extractor.py
│   │   │   ├── main.py
│   │   │   ├── refined_ir.py
│   │   │   └── tracing.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── semantic-bus-mcp
│       ├── semantic_bus
│       │   ├── __init__.py
│       │   ├── mcp_server.py
│       │   └── tracing.py
│       ├── Dockerfile
│       └── requirements.txt
├── shared_runtime
│   ├── __init__.py
│   ├── agent_keys.py
│   └── protocol.py
├── tests
│   ├── eval
│   │   ├── golden_delegation_cases.json
│   │   └── test_llm_delegation_golden.py
│   ├── load
│   │   └── locustfile.py
│   ├── scripts
│   │   ├── test_backup_dr_scripts.py
│   │   ├── test_build_refined_ir_catalog.py
│   │   ├── test_dedicated_agent_canary_rollout.py
│   │   ├── test_dedicated_agent_canary_trend.py
│   │   ├── test_dora_metrics_summary.py
│   │   ├── test_export_agent_model_inventory.py
│   │   ├── test_generate_agent_service_keys.py
│   │   ├── test_langgraph_postgres_recovery_qualification.py
│   │   ├── test_langgraph_v2_prototype_matrix.py
│   │   ├── test_mission_artifact_qualification.py
│   │   ├── test_operator_route_auth_matrix_qualification.py
│   │   ├── test_perf_smoke.py
│   │   ├── test_production_review_audit.py
│   │   ├── test_promotion_gate.py
│   │   ├── test_qualification_gate_summary.py
│   │   ├── test_reliability_qualification.py
│   │   ├── test_verify_backup_artifacts.py
│   │   └── test_verify_release_evidence.py
│   ├── security
│   │   ├── test_pod_assignment_conflict.py
│   │   └── test_state_mutation_auth.py
│   └── services
│       ├── test_agent_base_unit.py
│       ├── test_agent_core_unit.py
│       ├── test_agent_runtime_tracing_unit.py
│       ├── test_agent_runtime_unit.py
│       ├── test_agent_scaling.py
│       ├── test_api_gateway_auth_mode_unit.py
│       ├── test_api_gateway_live_stream_unit.py
│       ├── test_audit_worker_unit.py
│       ├── test_build_artifacts_unit.py
│       ├── test_concept_catalog.py
│       ├── test_dashboard_snapshot.py
│       ├── test_hardened_api_keys.py
│       ├── test_health.py
│       ├── test_langgraph_lifecycle_unit.py
│       ├── test_language_extractor.py
│       ├── test_live_extended_data_plane_integration.py
│       ├── test_live_mission_flow_integration.py
│       ├── test_llm_delegation_prompt_safety.py
│       ├── test_llm_delegation_retry_unit.py
│       ├── test_llm_delegation_unit.py
│       ├── test_migrations_unit.py
│       ├── test_milvus_store_unit.py
│       ├── test_mission_flow_unit.py
│       ├── test_mission_flow_v2.py
│       ├── test_neo4j_store_unit.py
│       ├── test_object_store_unit.py
│       ├── test_orchestrator_endpoints_extra.py
│       ├── test_orchestrator_lifecycle_recovery_unit.py
│       ├── test_pod_worker_consumer.py
│       ├── test_pod_worker_unit.py
│       ├── test_production_foundations.py
│       ├── test_protocol_and_auth.py
│       ├── test_qdrant_store_unit.py
│       ├── test_refined_ir_unit.py
│       ├── test_regression_contracts.py
│       ├── test_runtime_unit.py
│       ├── test_semantic_bus_mcp.py
│       ├── test_storage_unit.py
│       ├── test_tracing_unit.py
│       ├── test_tracing_wiring_unit.py
│       └── test_type_annotations.py
├── .coverage
├── .dockerignore
├── .editorconfig
├── .env.agent-service-keys.local
├── .env.example
├── .gitignore
├── AGENTS.md
├── BLUEPRINT_SPEC.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── coverage.xml
├── LICENSE
├── Makefile
├── pyproject.toml
├── README.md
├── requirements-dev.txt
├── ruff_errors.txt
├── SECURITY.md
├── start_app.bat
└── stop_app.bat
```
