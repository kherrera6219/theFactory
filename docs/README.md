# theFactory Docs

Document version: 2026.08.17
Last updated: 2026-08-17
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This directory contains the active documentation for theFactory. Historical
roadmaps, superseded plans, extracted source material, and old phase notes live
under `docs/archive/` and should not be used as current implementation truth.

## Start Here

| Need | Read |
|---|---|
| **Active initiative (start here if new)** | [UPGRADE_RECONCILIATION_PLAN_2026-08-01.md](UPGRADE_RECONCILIATION_PLAN_2026-08-01.md) — Phases 1–7, begin at its §0 "Cold start"; backed by [DESIGN_VS_BUILD_AUDIT_2026-08-01.md](DESIGN_VS_BUILD_AUDIT_2026-08-01.md) |
| Current state and open work | [CURRENT_TODO.md](CURRENT_TODO.md), [HANDOFF_CURRENT.md](HANDOFF_CURRENT.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [WORK_QUEUE.md](WORK_QUEUE.md) |
| Current initiative | [PM_SOW_FACTORY_PLAN_2026-08-17.md](PM_SOW_FACTORY_PLAN_2026-08-17.md) — PM-led SOW factory; live PORT + fail-QC recorded 2026-08-17 |
| Product scope | [00_PRODUCT_OVERVIEW.md](00_PRODUCT_OVERVIEW.md), [WHAT_THEFACTORY_IS_AND_IS_NOT.md](WHAT_THEFACTORY_IS_AND_IS_NOT.md) |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md), [ARCHITECTURE_DATA_FLOWS.md](ARCHITECTURE_DATA_FLOWS.md), [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) |
| API integration | [api/README.md](api/README.md), [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) |
| Local operation | [user/GETTING_STARTED.md](user/GETTING_STARTED.md), [user/OPERATOR_GUIDE.md](user/OPERATOR_GUIDE.md), [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) |
| Development workflow | [DEVELOPER_ONBOARDING_GUIDE.md](DEVELOPER_ONBOARDING_GUIDE.md), [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md), [TESTING_QUALITY_GATES.md](TESTING_QUALITY_GATES.md) |
| Complete map | [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) |

## Current Application Snapshot

theFactory is an active local-first AI software factory application, not a
production-ready release. The current runtime includes Mission Control,
api-gateway, orchestrator, protocol-bus MCP, pod workers, audit worker,
dedicated agent runtime containers, PostgreSQL, Redis, Qdrant, Milvus, Neo4j,
MinIO, and an observability stack.

Current validated proof points:

- PM-led SOW factory (P0–P4) is on `main`. Chat is the front door for new
  work and import; Accept SOW is the bid; CostPanel shows quoted vs actual
  vs cap; `sandbox-runner` owns `docker.sock`.
- Live PORT-through-SOW: `mission-dc0c8c4e` `COMPLETE`, official type
  `PORT`, files `go.mod` + `main.go`.
- Live failing-QC-blocks-COMPLETE: `mission-8db1af71` stayed `VERIFIED`
  with `MISSION_RUNTIME_QC_BLOCKED`. Evidence:
  [end_state_live_proof_20260817.json](evidence/end_state_live_proof_20260817.json).
- Live BUILD_NEW: Go S1-01 `mission-f8a5accf`, chat-driven PyQt6
  `mission-e42fd7e2`, stdlib Snake `mission-911a6b3f`.
- Coverage gates: line ≥80%, branch ≥70%, mixed ≥80%. Every critical
  file is floored at **at least 80%** (`rqca_agent`, `sow_estimator`,
  `file_tree`, `port_coordinator`, sandbox/SOW). Latest sweep: line
  85.80%, branch 72.82%, mixed 82.72%. A mixed score above 80% cannot
  hide a line score below 80%.
- Production audit (`production_review_audit.py`) is a hygiene check, not
  a release certificate.

Tracked remaining gaps:

- Chat ZIP UI walkthrough (API path is proven).
- Live failure-injection and provider-fallback proof.
- One-mission EDCP live-bus (`EVENT_DRIVEN_CONTROL_PLANE_ENABLED=true`).
- Public hosting, customer isolation, and a production auth story.

## Maintenance Rules

- Keep current operational truth in this directory.
- Move superseded plans and historical audits to `docs/archive/`.
- Keep generated or run-specific evidence under `docs/evidence/`.
- Do not duplicate current-state summaries across many files; prefer this page,
  [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), and
  [CURRENT_TODO.md](CURRENT_TODO.md).
