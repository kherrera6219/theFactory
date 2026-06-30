# theFactory Docs

Document version: 2026.06.30
Last updated: 2026-06-30
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This directory contains the active documentation for theFactory. Historical
roadmaps, superseded plans, extracted source material, and old phase notes live
under `docs/archive/` and should not be used as current implementation truth.

## Start Here

| Need | Read |
|---|---|
| Current state and open work | [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [CURRENT_TODO.md](CURRENT_TODO.md), [HANDOFF_CURRENT.md](HANDOFF_CURRENT.md) |
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

- Phase 13 backend/API smoke passed on 2026-06-30 with mission
  `mission-ac933664-bda8-4acf-b265-10171c2ccdf6`, which reached `COMPLETE`,
  retrieved one build artifact, and passed Python syntax validation for that
  artifact.
- Phase 3 non-ASCII artifact evidence passed with mission
  `mission-bd5369ec-3777-4099-89fe-81699289a29d`, preserving 28 non-ASCII
  characters through codegen, packaging, and storage readback.
- Phase 8 Mission Flow v2 line coverage now clears the older 90% target; the
  broader related suite passed 170 tests at 92.43% line / 74.70% branch.
- Production audit passes 23/23 checks after closing `INF-008`.
- CodeQL alerts #337-#338 and Trivy OpenSSL alerts #330-#336 have local
  remediation through parser-based RQCA HTML smoke, raster-only file previews,
  and refreshed Python service base-image digests.
- Documentation validation and OpenAPI drift checks are enforced through
  `make validate`.

Tracked remaining gaps:

- Mission Control UI smoke for the Phase 13 mission path.
- Live failure-injection and provider-fallback proof.
- Full `make validate` in the current environment.
- Remaining Phase 8 `mission_flow_v2/` branch-coverage carry-forward or
  explicit deferral of the old 85% branch target.

## Maintenance Rules

- Keep current operational truth in this directory.
- Move superseded plans and historical audits to `docs/archive/`.
- Keep generated or run-specific evidence under `docs/evidence/`.
- Do not duplicate current-state summaries across many files; prefer this page,
  [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), and
  [CURRENT_TODO.md](CURRENT_TODO.md).
